"""In-memory wallet tests for monetary conversion and payment retries.

Amounts use integer minor units. Conversion uses the supplied currency exponent
and HALF_EVEN rounding. Repeated request keys refer to the same payment.
"""
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import io
import unittest


class BuggyWallet:
    """Three intentional defects: fixed exponent, wrong rounding, no replay."""

    def __init__(self, balance_minor=10000):
        self.balance_minor = balance_minor
        self.postings = []
        self.results = {}

    @staticmethod
    def to_minor(amount, exponent):
        return int((Decimal(amount) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    def charge(self, amount, exponent, key):
        return self._post(amount, exponent, key)

    def _post(self, amount, exponent, key):
        minor = self.to_minor(amount, exponent)
        if minor <= 0 or minor > self.balance_minor:
            raise ValueError('Amount must be positive and within available funds')
        self.balance_minor -= minor
        receipt = {'posting_id': len(self.postings) + 1, 'amount_minor': minor}
        self.postings.append(receipt)
        self.results[key] = ((Decimal(amount), exponent), receipt)
        return receipt


class FixedWallet(BuggyWallet):
    """Fix the three fixture defects; concurrency and persistence are omitted."""

    @staticmethod
    def to_minor(amount, exponent):
        return int((Decimal(amount) * (10 ** exponent)).quantize(
            Decimal('1'), rounding=ROUND_HALF_EVEN))

    def charge(self, amount, exponent, key):
        if key in self.results:
            payload, receipt = self.results[key]
            if payload != (Decimal(amount), exponent):
                raise ValueError('Idempotency key payload conflict')
            return receipt
        return self._post(amount, exponent, key)


def make_tests(wallet_type):
    class WalletTests(unittest.TestCase):
        def test_single_payment(self):
            wallet = wallet_type(balance_minor=10000)
            receipt = wallet.charge('12.34', exponent=2, key='payment-1')
            self.assertEqual(receipt['amount_minor'], 1234)
            self.assertEqual(wallet.balance_minor, 8766)
            self.assertEqual(len(wallet.postings), 1)

        def test_currency_exponent(self):
            self.assertEqual(wallet_type.to_minor('1.234', exponent=3), 1234)

        def test_half_even_rounding(self):
            self.assertEqual(wallet_type.to_minor('1.005', exponent=2), 100)

        def test_duplicate_request(self):
            wallet = wallet_type(balance_minor=10000)
            first = wallet.charge('12.34', exponent=2, key='payment-1')
            second = wallet.charge('12.34', exponent=2, key='payment-1')
            self.assertEqual(wallet.balance_minor, 8766)
            self.assertEqual(len(wallet.postings), 1)
            self.assertEqual(second['posting_id'], first['posting_id'])

    return WalletTests


def run_case(label, wallet_type, methods, expected_failures):
    tests = make_tests(wallet_type)
    suite = unittest.TestSuite(tests(method) for method in methods)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    failures = {test._testMethodName for test, _ in result.failures}
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f'{label}: {passed} passed, {len(result.failures)} failed, {len(result.errors)} errors')
    for method in sorted(failures):
        print(f'  FAIL {method}')
    if failures != expected_failures or result.errors or result.testsRun != len(methods):
        print(log.getvalue())
        raise SystemExit('Unexpected demo result')


def main():
    basic = ['test_single_payment']
    expanded = basic + ['test_currency_exponent', 'test_half_even_rounding', 'test_duplicate_request']
    run_case('Basic example / buggy code', BuggyWallet, basic, set())
    run_case('Fintech examples / buggy code', BuggyWallet, expanded, set(expanded[1:]))
    run_case('Fintech examples / fixed code', FixedWallet, expanded, set())
    print('Demo reproduced: all three intentional defects were detected.')


if __name__ == '__main__':
    main()

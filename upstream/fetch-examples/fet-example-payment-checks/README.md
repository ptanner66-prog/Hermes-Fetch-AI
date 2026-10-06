# Fix for Fetch.ai's FET payment example

A contribution to [fetchai/innovation-lab-examples](https://github.com/fetchai/innovation-lab-examples), Fetch.ai's Innovation Lab examples. Its `fet-example` is the reference ASI:One's FET payment card is built from. Its seller checks payments on the ledger, but it trusts the buyer's stated amount, accepts one payment again and again, rounds prices through floats, and sees only the last of several transfers. [`PR.md`](PR.md) explains each problem and the fix, with before-and-after results.

Prepared against commit `ae840c28001b266a99e390e6e7d35cbe809b9f05` (2026-09-01). If `fet-example/payment.py` has changed since, re-check before submitting.

## Files

- [`fet-example-payment-checks.patch`](fet-example-payment-checks.patch) changes `fet-example/payment.py` and adds `fet-example/verify.py`.
- [`check_payment.py`](check_payment.py) drives the example's `CommitPayment` handler against a stand-in ledger, with no network. Run it before and after applying the patch.
- [`PR.md`](PR.md) is the pull request text.

## Submit it

The examples repo welcomes community pull requests ([CONTRIBUTING.md](https://github.com/fetchai/innovation-lab-examples/blob/main/CONTRIBUTING.md)). It asks you to star the repository first, branch from `main`, and keep each PR to one fix. Every PR is reviewed before merge.

1. Star [fetchai/innovation-lab-examples](https://github.com/fetchai/innovation-lab-examples) and fork it on GitHub.
2. Clone your fork, then apply and check the patch. The check needs uagents, uagents-core, and cosmpy, which `fet-example/requirements.txt` lists:

   ```bash
   git clone https://github.com/<you>/innovation-lab-examples
   cd innovation-lab-examples
   git checkout -b fix/fet-example-payment-checks
   python <this folder>/check_payment.py fet-example   # before: 4 FAIL
   git apply <this folder>/fet-example-payment-checks.patch
   python <this folder>/check_payment.py fet-example   # after: 8 PASS
   ```

3. Commit with your GitHub noreply address, which keeps your personal email out of their history, then push:

   ```bash
   git add fet-example/payment.py fet-example/verify.py
   git -c user.name=ptanner66-prog \
       -c user.email=236672476+ptanner66-prog@users.noreply.github.com \
       commit -m "fix(fet-example): check FET payments against the seller's price, once per transaction"
   git push -u origin fix/fet-example-payment-checks
   ```

4. On GitHub, open a pull request to `fetchai/innovation-lab-examples:main`. Title: `fet-example: check FET payments against the seller's price, once per transaction`. Body: [`PR.md`](PR.md).

Our own CI checks the patch's `verify.py` (`tests/test_upstream_fet_example.py`), so it stays correct if it is edited here.

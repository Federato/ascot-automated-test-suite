# Ascot Automated Test Suite

Selenium tests for the Federato underwriting portal (`ascotus-dev`).

## Current tests

| Test | What it does |
| --- | --- |
| `test_create_es_submission` | Logs in, creates an E&S submission, finds the new account on the Accounts page, opens it, and checks the account detail page. |

## Prerequisites

Install these before you start:

- **Python 3.10 or newer** (`python3 --version` to check). On macOS: `brew install python`
- **Git** (`git --version` to check)
- **Google Chrome**, up to date. Selenium downloads a matching ChromeDriver automatically on first run, so you do not need to install it yourself. This needs normal internet access.
- **A Federato `ascotus-dev` account** that can create E&S submissions

## Setup

```bash
git clone https://github.com/Federato/ascot-automated-test-suite.git
cd ascot-automated-test-suite

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Create your credentials file:

```bash
cp .env.example .env
```

Then open `.env` and fill in your values (no quotes, no spaces around `=`):

```
FEDERATO_USER=your-email@example.com
FEDERATO_PASS=your-password
```

If your password contains `#` or `$`, wrap it in single quotes: `FEDERATO_PASS='pa#ss'`.

`.env` is listed in `.gitignore`. Never commit it.

## Run

Activate the virtual environment first (look for `(.venv)` in your terminal prompt), then:

```bash
pytest test_es_submission.py -s
```

`-s` shows print output. A Chrome window opens and you can watch the test run.

To run every test in the repo:

```bash
pytest -s
```

## Logging in with SSO

The login page offers username/password and Azure AD SSO. The test fills in the username/password form, so it needs an account on that connection. If your account only works through SSO, automated login will not work. Options:

1. Ask your admin for a dedicated test user with username/password login.
2. Log in manually once and reuse the session by adding this line to the `driver` fixture in the test file, then log in by hand in the window that opens on the first run:

   ```python
   opts.add_argument("--user-data-dir=/absolute/path/to/.chrome-profile")
   ```

   The test skips the login form whenever the browser is already signed in. `.chrome-profile/` is gitignored.

## Test data

- Each run creates a **real account and submission** in `ascotus-dev` named `Selenium Test Co <timestamp>`. These are not cleaned up automatically.
- The agency (`Acentria Insurance - Ormond Beach, FL`) and agent (`Jo Chonko`) are hardcoded in the test. If they are removed or renamed in the environment, update them in `test_es_submission.py`.

## Configuration

| Setting | Where | Notes |
| --- | --- | --- |
| Portal URL | `BASE_URL`, `ACCOUNTS_URL` in `test_es_submission.py` | Point at another environment by changing the host |
| Credentials | `.env` | `FEDERATO_USER`, `FEDERATO_PASS` |
| Headless mode | `driver` fixture | Uncomment `--headless=new` to run without a visible window (CI) |

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `command not found: pytest` | The virtual environment is not active. Run `source .venv/bin/activate`. |
| `command not found: pip` | Use `pip3`, or activate the virtual environment, which provides `pip`. |
| `KeyError: 'FEDERATO_USER'` | `.env` is missing, misnamed, or in the wrong folder. It must sit next to `test_es_submission.py`. |
| Times out after clicking Continue on login | Wrong credentials, MFA prompt, or an SSO-only account. See "Logging in with SSO". |
| Agency or agent dropdown stays empty | The data did not load in time or the session is not fully authenticated. Rerun, and check the Network tab for failed requests. |
| `TimeoutException` on the account search | Newly created accounts can take a few seconds to appear in search. Rerun; if it persists, check that the submission was actually created. |
| `externally-managed-environment` when running `pip install` | You are installing outside a virtual environment. Create and activate `.venv` first. |

# test_es_submission.py
import os
import pytest
import sys
from dotenv import load_dotenv, set_key
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


load_dotenv()
BASE_URL = "https://ascotus-dev.federato.ai/uw-portal/home"
ACCOUNTS_URL = "https://ascotus-dev.federato.ai/uw-portal/accounts"
DIALOG = "[data-testid='athena-modal']"
SELECT_ALL = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL


@pytest.fixture
def driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--window-size=1600,1000")
    # opts.add_argument("--headless=new")  # enable in CI
    d = webdriver.Chrome(options=opts)
    yield d
    d.quit()


@pytest.fixture
def wait(driver):
    return WebDriverWait(driver, 20)


def click(wait, locator):
    wait.until(EC.element_to_be_clickable(locator)).click()


def type_into(wait, locator, text):
    el = wait.until(EC.visibility_of_element_located(locator))
    el.clear()
    el.send_keys(text)

import time



def fill(wait, name, text):
    type_into(wait, (By.CSS_SELECTOR, f"{DIALOG} input[name='{name}']"), text)


def pick_combobox(wait, name, search_text=None, option_text=None, pick_first=False):
    inp = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, f"{DIALOG} input[name='{name}']")))
    inp.click()

    if search_text:
        for ch in search_text:          # type like a person, not instantly
            inp.send_keys(ch)
            time.sleep(0.08)
    else:
        # open the list via the chevron button in the same wrapper
        inp.find_element(
            By.XPATH, "following-sibling::div//button[@aria-label='Show suggestions']"
        ).click()

    options = (By.XPATH, "//*[@role='option']")
    wait.until(EC.presence_of_element_located(options))   # wait for data to load
    time.sleep(0.5)                                       # let the list settle after filtering

    if pick_first:
        click(wait, (By.XPATH, "(//*[@role='option'])[1]"))
    else:
        want = option_text or search_text
        click(wait, (By.XPATH,
                     f"//*[@role='option'][contains(normalize-space(.), '{want}')]"))


def fill_date(wait, label, mmddyyyy):
    seg = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, f"{DIALOG} [role='spinbutton'][aria-label='month, {label}']")))
    seg.click()
    seg.send_keys(mmddyyyy)  # e.g. "12012026", focus auto-advances month -> day -> year


from selenium.common.exceptions import TimeoutException

def login(driver, wait):
    driver.get(BASE_URL)

    # If the browser profile is already authenticated, we're redirected straight in
    try:
        WebDriverWait(driver, 5).until(EC.url_contains("/uw-portal"))
        return
    except TimeoutException:
        pass
    
    print("user len:", len(os.environ.get("FEDERATO_USER", "")))
    print("pass len:", len(os.environ.get("FEDERATO_PASS", "")))

    type_into(wait, (By.ID, "username"), os.environ["FEDERATO_USER"])
    type_into(wait, (By.ID, "password"), os.environ["FEDERATO_PASS"])
    click(wait, (By.CSS_SELECTOR, "form[data-form-primary='true'] button[type='submit']"))

    wait.until(EC.url_contains("/uw-portal"))

def find_account_link(driver, wait, account_name, attempts=4):
    driver.get(ACCOUNTS_URL)

    search = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "input[aria-label='Search'][placeholder='Search']")))

    # The row's navigation is an invisible overlay <a>; find the row by exact name
    row_link = (By.XPATH,
                f"//div[@role='row'][.//span[normalize-space()='{account_name}']]"
                "//a[contains(@class,'athena-table-primary-action')]")

    for _ in range(attempts):
        search.send_keys(SELECT_ALL, "a")
        search.send_keys(account_name)
        try:
            return WebDriverWait(driver, 8).until(
                EC.presence_of_element_located(row_link))
        except TimeoutException:
            time.sleep(3)  # new records can take a moment to appear in search

    raise AssertionError(f"Account '{account_name}' never appeared in the accounts table")


def assert_account_details(driver, wait, account_name):
    wait.until(EC.url_matches(r"/uw-portal/accounts/\d+"))

    # Saved account name matches what we created
    name_input = wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, "input[name='account_name']")))
    assert name_input.get_attribute("value") == account_name

    # E&S line-of-business tab exists
    wait.until(EC.visibility_of_element_located(
        (By.XPATH, "//div[@role='tab'][.//p[normalize-space()='E&S']]")))

    # Policies table has an E&S group; expand it
    group_row = wait.until(EC.visibility_of_element_located(
        (By.XPATH,
         "//*[@data-testid='widget-table-all-accounts-general-all-policies-tb']"
         "//div[@role='row'][.//span[normalize-space()='E&S']]")))
    group_row.find_element(
        By.XPATH, ".//button[.//span[normalize-space()='Expand group']]").click()


SKIP_PAUSE = 2  # seconds to linger on a page before skipping a step
ERROR_WORDS = ("missing", "error", "fail", "will not proceed", "unable", "invalid")
TOAST = (By.CSS_SELECTOR, "[role='status'][aria-live='polite']")


def toast_texts(driver):
    return [t.text.strip() for t in driver.find_elements(*TOAST) if t.text.strip()]


def wait_toasts_gone(driver, timeout=15):
    """Wait for leftover toasts from earlier actions to disappear, so an old
    toast can't be mistaken for the result of the next action."""
    WebDriverWait(driver, timeout).until(lambda d: not toast_texts(d))


def wait_for_success_toast(driver, timeout=45):
    """Wait for a toast containing "success" (react-hot-toast, role='status').
    Other toasts (e.g. a loading/in-progress one) are ignored while we keep waiting.
    Fails immediately if an error toast shows up. Returns the success toast's text."""
    end = time.time() + timeout
    seen = []
    while time.time() < end:
        for text in toast_texts(driver):
            if text not in seen:
                seen.append(text)
            if any(w in text.lower() for w in ERROR_WORDS):
                raise AssertionError(f"Error toast shown: {text}")
            if "success" in text.lower():
                return text
        time.sleep(0.25)
    raise AssertionError(f"No success toast within {timeout}s. Toasts seen: {seen}")


def test_clear_es_submission_policy(driver, wait):
    login(driver, wait)

    name = os.environ.get("ACCOUNT_NAME", "")

    link = find_account_link(driver, wait, name)
    assert "/uw-portal/accounts/" in link.get_attribute("href")

    # The link is an invisible overlay with no size of its own, so click it via JS
    driver.execute_script("arguments[0].click()", link)

    assert_account_details(driver, wait, name)

    # Set the account Type (required) on the Details form and save, only if it is empty
    type_input_locator = (By.CSS_SELECTOR, "input[name='entity_type']")
    type_input = wait.until(EC.presence_of_element_located(type_input_locator))
    # Scroll to the middle of the view so the sticky tab bar doesn't cover the field
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", type_input)
    if type_input.get_attribute("value").strip():
        print("Type already set, skipping:", type_input.get_attribute("value"))
        time.sleep(SKIP_PAUSE)  # pause so the skip is visible when watching
    else:
        wait.until(EC.element_to_be_clickable(type_input_locator)).click()
        time.sleep(0.5)
        if type_input.get_attribute("aria-expanded") != "true":
            # Open the list via the chevron next to the input
            type_input.find_element(
                By.XPATH, "following-sibling::div//button | following::button[1]").click()
        corp_option = (By.XPATH, "//*[@role='option'][normalize-space()='Corporation']")
        wait.until(EC.presence_of_element_located(corp_option))
        time.sleep(0.5)
        driver.execute_script("arguments[0].click()", driver.find_element(*corp_option))
        # Submit button of the same form as the Type field
        submit_btn = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@name='entity_type']/ancestor::form//button[@type='submit']")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", submit_btn)
        wait.until(EC.element_to_be_clickable(submit_btn)).click()
        time.sleep(3)  # let the save finish
        type_errors = [t.text for t in driver.find_elements(
            By.CSS_SELECTOR, "[role='status'][aria-live='polite']")
            if any(w in t.text.lower() for w in ("error", "fail", "unable", "invalid"))]
        assert not type_errors, f"Saving account type failed: {type_errors}"

    # Account Type is set (either already was, or we just saved it)
    assert driver.find_element(By.CSS_SELECTOR, "input[name='entity_type']") \
        .get_attribute("value").strip(), "Account Type is empty after saving"

    # Open the E&S line-of-business tab
    click(wait, (By.XPATH, "//div[@role='tab'][.//p[normalize-space()='E&S']]"))
    wait.until(EC.url_contains("/lines/"))

    # Open the first policy whose status is "Clearance Pending"
    pending_row_link = (By.XPATH,
        "//div[@role='row'][contains(normalize-space(.), 'Clearance Pending')]"
        "//a[contains(@class,'athena-table-primary-action')]")
    # Wait for the policies table to finish loading (rows, or the "No data" message)
    wait.until(lambda d: d.find_elements(
        By.XPATH, "//div[@role='row']//a[contains(@class,'athena-table-primary-action')]")
        or d.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'No data was found')]"))
    # Nothing left to clear -> skip the rest of the test
    if not driver.find_elements(*pending_row_link):
        time.sleep(SKIP_PAUSE)  # pause so the table is visible before skipping
        pytest.skip("No policies with status 'Clearance Pending'; all already cleared")
    policy_link = wait.until(EC.presence_of_element_located(pending_row_link))
    driver.execute_script("arguments[0].click()", policy_link)
    wait.until(EC.url_contains("policyId="))

    # Assign an underwriter (required before clearing): Broker & Contact section
    uw_input = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[name='underwriter_users']")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", uw_input)
    # Skip if an underwriter is already assigned (an empty field shows "(Unassigned)")
    current_uw = (uw_input.get_attribute("value") or "").strip()
    if current_uw and "unassigned" not in current_uw.lower():
        print("Underwriter already assigned, skipping:", current_uw)
        time.sleep(SKIP_PAUSE)  # pause so the skip is visible when watching
    else:
        # Open the list with the chevron button next to the input
        wait.until(EC.element_to_be_clickable((By.XPATH,
            "//input[@name='underwriter_users']"
            "/following-sibling::div//button[@aria-label='Show suggestions']"))).click()
        first_option = (By.XPATH, "(//*[@role='option'])[1]")
        wait.until(EC.presence_of_element_located(first_option))   # wait for users to load
        time.sleep(0.5)                                            # let the list settle
        # Use a real click (a JS .click() doesn't always register with the React combobox,
        # so the selection never reaches the form state and nothing gets saved)
        wait.until(EC.element_to_be_clickable(first_option)).click()

        # The field must now show a user rather than "(Unassigned)"
        wait.until(lambda d: "unassigned" not in
                   (d.find_element(By.CSS_SELECTOR, "input[name='underwriter_users']")
                    .get_attribute("value") or "").lower())

        # Submit the same form the underwriter field belongs to
        uw_submit = driver.find_element(
            By.XPATH, "//input[@name='underwriter_users']/ancestor::form//button[@type='submit']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", uw_submit)
        wait_toasts_gone(driver)   # make sure any older toast is gone first
        wait.until(EC.element_to_be_clickable(uw_submit)).click()

        # Wait for the underwriter save to succeed before moving on
        print("Underwriter saved:", wait_for_success_toast(driver))
        wait_toasts_gone(driver)

    # An underwriter is now assigned
    final_uw = driver.find_element(By.CSS_SELECTOR, "input[name='underwriter_users']") \
        .get_attribute("value").strip()
    assert final_uw and "unassigned" not in final_uw.lower(), \
        f"Underwriter not assigned (field shows '{final_uw}')"

    # Remember how many "Cleared" statuses are on the page so we can confirm one more after
    cleared_status = (By.XPATH, "//*[normalize-space(text())='Cleared']")
    cleared_before = len(driver.find_elements(*cleared_status))

    # Change Status -> Cleared
    # The page was scrolled down to reach the underwriter field, which leaves the
    # button under the header, so scroll it back into view before clicking
    status_btn = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "[data-testid='change-status-button']")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", status_btn)
    wait.until(EC.element_to_be_clickable(status_btn)).click()
    click(wait, (By.XPATH, "//*[@role='menuitem']"
                           "[normalize-space()='Cleared']"))

    # Fill in the Clear Submission dialog and submit
    wait.until(EC.visibility_of_element_located(
        (By.XPATH, "//*[normalize-space()='Clear Submission']")))
    type_into(wait, (By.CSS_SELECTOR, f"{DIALOG} textarea"), "Testing clearing policy")
    click(wait, (By.XPATH, "//*[@data-testid='athena-modal']//button[normalize-space()='Submit']"))

    # Wait for the clearing to succeed (an error toast fails the test immediately)
    clear_toast = wait_for_success_toast(driver)
    print("Policy cleared:", clear_toast)
    assert "success" in clear_toast.lower()

    # Dialog closes on success
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, DIALOG)))

    # The page now shows one more "Cleared" status than before
    wait.until(lambda d: len(d.find_elements(*cleared_status)) > cleared_before,
               "Policy status on the page never changed to Cleared")

    print('DONE!')

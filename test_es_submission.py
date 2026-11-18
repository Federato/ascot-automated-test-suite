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
    
    print('DONE!')


def test_create_es_submission(driver, wait):
    login(driver, wait)

    # Navigate to E&S Section
    click(wait, (By.XPATH, "//button[contains(., 'E&S UW Home')]"))

    # Create submission
    click(wait, (By.XPATH, "//button[contains(., 'Create')]"))

    wait.until(EC.visibility_of_element_located(
    (By.CSS_SELECTOR, "[data-testid='athena-modal']")))

    name = f"Selenium Test Co {int(time.time())}"

    # Account Information (Account defaults to "(Create New Account)")
    fill(wait, "insured_name", name)
    fill(wait, "address_1", "123 Main St")
    fill(wait, "city", "Portland")
    pick_combobox(wait, "state", "Oregon")   # adjust if options are abbreviations like "OR"
    fill(wait, "zip_code", "97201")

    # Policy Information (Renewal or New Business defaults to NEW BUSINESS)
    fill_date(wait, "Effective Date", "12012026")
    fill_date(wait, "Expiration Date", "12012027")
    pick_combobox(wait, "lob_id", "E&S")     # use the real LOB name, or a substring of it

    # Broker Information
    pick_combobox(wait, "broker_id", "Acentria Insurance - Ormond Beach, FL")
    pick_combobox(wait, "broker_contact_id", "Jo Chonko")

    click(wait, (By.CSS_SELECTOR, f"{DIALOG} button[type='submit']"))

    # Modal closes on success
    wait.until(EC.invisibility_of_element_located(
        (By.CSS_SELECTOR, "[data-testid='athena-modal']")))


    # Go to the accounts page, find the new account, and open it
    link = find_account_link(driver, wait, name)
    assert "/uw-portal/accounts/" in link.get_attribute("href")

    # The link is an invisible overlay with no size of its own, so click it via JS
    driver.execute_script("arguments[0].click()", link)

    assert_account_details(driver, wait, name)

    # Save account name to env file so can use to run other tests
    set_key(".env", "ACCOUNT_NAME", name)
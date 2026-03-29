"""
Twitter/X profile scraper using Selenium and BeautifulSoup.

Logs into X, navigates to a user's profile, and scrolls through their timeline
collecting tweet data until a configurable stop condition is met (or a maximum
tweet count is reached). Results are saved to a JSON file.

Usage:
    python scraper.py

    Credentials can be set via environment variables (see .env.example) or
    entered interactively at runtime.
"""

import getpass
import json
import os
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

TARGET_USERNAME = os.getenv("TARGET_USERNAME") or input("Username to scrape: ")
LOGIN_USERNAME = os.getenv("LOGIN_USERNAME") or input("Login username: ")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD") or getpass.getpass("Login password: ")

# The scraper stops early when it encounters this tweet text.
STOP_AT_TWEET = os.getenv("STOP_AT_TWEET", "")

# Maximum number of tweets to collect before stopping.
MAX_TWEETS = int(os.getenv("MAX_TWEETS", "2000"))

OUTPUT_FILE = os.getenv("OUTPUT_FILE", "tweets_dump.json")

BASE_URL = "https://x.com"


def parse_tweets(page_source: str, target_username: str) -> list:
    """Parse tweet elements from a page's HTML source.

    Args:
        page_source: Raw HTML of the current page body.
        target_username: The X username whose timeline is being scraped.
            Used to locate the correct timeline container.

    Returns:
        A list of BeautifulSoup tag objects, one per tweet cell.
    """
    soup = BeautifulSoup(page_source, "html.parser")

    timeline = soup.find(
        "div",
        class_="css-175oi2r",
        attrs={"aria-label": f"Timeline: {target_username}'s posts"},
    )

    if not timeline:
        return []

    return list(
        timeline.find_all(
            "div", class_="css-175oi2r", attrs={"data-testid": "cellInnerDiv"}
        )
    )


def find_username(tweet_element) -> str:
    """Extract the display name and handle from a tweet element.

    Args:
        tweet_element: A BeautifulSoup tag representing a single tweet cell.

    Returns:
        The username text, or an empty string if not found.
    """
    el = tweet_element.find(
        "div", class_="css-175oi2r", attrs={"data-testid": "User-Name"}
    )
    return el.text.strip() if el else ""


def find_text(tweet_element) -> str:
    """Extract the text content of a tweet.

    Args:
        tweet_element: A BeautifulSoup tag representing a single tweet cell.

    Returns:
        The tweet text, or an empty string if not found.
    """
    el = tweet_element.find(
        "div", class_="css-146c3p1", attrs={"data-testid": "tweetText"}
    )
    if not el:
        return ""
    return " ".join(child.text.strip() for child in el.children if child.name == "span")


def find_image(tweet_element) -> str:
    """Extract the URL of the first image attached to a tweet.

    Args:
        tweet_element: A BeautifulSoup tag representing a single tweet cell.

    Returns:
        The image src URL, or an empty string if no image is present.
    """
    el = tweet_element.find(
        "div", class_="css-175oi2r", attrs={"data-testid": "tweetPhoto"}
    )
    if not el:
        return ""
    for child in el.children:
        if child.name == "img":
            return child["src"]
    return ""


def find_url(tweet_element) -> str:
    """Extract the permalink URL from a tweet element.

    Args:
        tweet_element: A BeautifulSoup tag representing a single tweet cell.

    Returns:
        The href of the tweet link, or an empty string if not found.
    """
    el = tweet_element.find("a", class_="css-1rynq56")
    return el.get("href", "") if el else ""


def find_profile_type(tweet_element) -> str:
    """Extract the profile type label (e.g. 'Following') from a tweet element.

    Args:
        tweet_element: A BeautifulSoup tag representing a single tweet cell.

    Returns:
        The profile type text, or an empty string if not found.
    """
    el = tweet_element.find(
        "div",
        class_=(
            "css-1rynq56 r-dnmrzs r-1udh08x r-3s2u2q r-bcqeeo r-qvutc0 "
            "r-37j5jr r-a023e6 r-rjixqe r-16dba41"
        ),
    )
    if not el:
        return ""
    for child in el.children:
        if child.name == "span":
            return child.text
    return ""


def get_tweet_data(tweet_element) -> dict | None:
    """Build a dictionary of data extracted from a single tweet element.

    Recursively handles quoted tweets. Returns None if no meaningful data
    could be extracted.

    Args:
        tweet_element: A BeautifulSoup tag representing a single tweet cell
            or quoted tweet container.

    Returns:
        A dict with any of the keys Username, Image, Tweet, url,
        profile_type, and quoted_tweet — or None if the element is empty.
    """
    data = {}

    if username := find_username(tweet_element):
        data["Username"] = username
    if image := find_image(tweet_element):
        data["Image"] = image
    if text := find_text(tweet_element):
        data["Tweet"] = text
    if url := find_url(tweet_element):
        data["url"] = url
    if profile_type := find_profile_type(tweet_element):
        data["profile_type"] = profile_type

    quoted = tweet_element.find("div", class_="css-175oi2r", attrs={"role": "link"})
    if quoted:
        data["quoted_tweet"] = get_tweet_data(quoted)

    return data if data else None


def scroll_down(driver, scroll_amount: int = 1000) -> None:
    """Scroll the page down by a given number of pixels.

    Args:
        driver: The Selenium WebDriver instance.
        scroll_amount: Number of pixels to scroll. Defaults to 1000.
    """
    driver.execute_script(f"window.scrollTo(0, window.scrollY + {scroll_amount})")


def login(driver, username: str, password: str) -> None:
    """Log into X using the provided credentials.

    Navigates to the X login flow, fills in the username and password,
    and waits for the direct messages tab to confirm a successful login.

    Args:
        driver: The Selenium WebDriver instance.
        username: The X account username (without @).
        password: The account password.

    Raises:
        selenium.common.exceptions.TimeoutException: If any expected element
            is not found within the wait timeout.
    """
    driver.get("https://twitter.com/i/flow/login")
    wait = WebDriverWait(driver, 10)

    username_field = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[autocomplete=username]")
        )
    )
    username_field.send_keys(username)

    next_button = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[role=button].r-13qz1uu"))
    )
    next_button.click()

    password_field = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[type=password]"))
    )
    password_field.send_keys(password)

    login_button = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid*=Login_Button]"))
    )
    login_button.click()

    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[data-testid=AppTabBar_DirectMessage_Link]")
        )
    )
    print(f"Successfully logged in as @{username}")


def scrape_profile(
    driver,
    target_username: str,
    max_tweets: int,
    stop_at_tweet: str,
    scroll_amount: int,
) -> list:
    """Scrape tweets from a user's profile page.

    Scrolls through the profile timeline, collecting unique tweets until
    either max_tweets is reached or the stop_at_tweet text is encountered.

    Args:
        driver: The Selenium WebDriver instance, already logged in.
        target_username: The X username of the profile to scrape.
        max_tweets: Maximum number of tweets to collect.
        stop_at_tweet: If non-empty, stop when a tweet with this exact text
            is found.

    Returns:
        A list of tweet data dicts.
    """
    driver.get(f"{BASE_URL}/{target_username}")
    time.sleep(5)

    collected = []
    scroll_count = 0

    print("Scraping...")

    while len(collected) < max_tweets:
        html = driver.execute_script("return document.body.innerHTML;")
        tweets = parse_tweets(html, target_username)

        for tweet in tweets:
            if content := get_tweet_data(tweet):
                if content not in collected:
                    collected.append(content)

        scroll_down(driver, scroll_amount=scroll_amount)
        scroll_count += 1
        time.sleep(0.1)

        if collected:
            print(collected[-1])
            if stop_at_tweet and collected[-1].get("Tweet") == stop_at_tweet:
                print("Stop condition reached.")
                break

    print(f"Scrolled {scroll_count} times.")
    print(f"Retrieved {len(collected)} tweets.")
    return collected


def main():
    """Entry point: log in, scrape, and save results to JSON."""
    driver = webdriver.Chrome()
    try:
        login(driver, LOGIN_USERNAME, LOGIN_PASSWORD)
        tweets = scrape_profile(driver, TARGET_USERNAME, MAX_TWEETS, STOP_AT_TWEET)
    finally:
        driver.quit()

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"tweets": tweets}, f)

    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

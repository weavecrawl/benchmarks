"""The person, simulated: a headless Playwright browser opens an approval link and presses one button.

    python3 person.py URL [BUTTON-TEXT] [--value TEXT] [--own-host HOST]

Prints the page text and the buttons it offers. With BUTTON-TEXT it presses that button (for example
"Approve once", "Deny" or "Done") and prints what the page says after; with --value it first
types TEXT into the page's one value box (the secret page). With --own-host it presses an approving button only when the
page names that host: an approval is given on the own test site and nowhere else. Only for links of a scratch brain: a
link is a secret, so this script prints the page, never the link.
"""
import argparse
import asyncio

APPROVING = ("approve", "always allow")


def refuses(button, page_text, own_host):
    """Whether the person must not press `button`: an approving button on a page that does not name the own host."""
    return bool(own_host) and any(w in (button or "").lower() for w in APPROVING) and own_host.lower() not in page_text.lower()


async def act(url, button=None, value=None, own_host=None, headless=True):
    from playwright.async_api import async_playwright
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=headless, args=["--password-store=basic", "--use-mock-keychain"])
        pg = await b.new_page()
        r = await pg.goto(url)
        out["status"] = r.status if r else None
        out["title"] = await pg.title()
        text = await pg.inner_text("body")
        out["text"] = (out["title"] + "\n" + text)[:1500]
        out["buttons"] = await pg.eval_on_selector_all(
            "button,input[type=submit]", "els=>els.map(e=>e.innerText||e.value)")
        if button:
            if refuses(button, out["title"] + "\n" + text, own_host):
                out["refused"] = f"page does not name {own_host}: {button!r} not pressed"
            else:
                if value is not None:
                    await pg.fill("input[name=value]", value)
                try:
                    await pg.get_by_role("button", name=button).click(timeout=8000)
                    await pg.wait_for_load_state()
                    out["after"] = (await pg.inner_text("body"))[:600]
                except Exception as e:  # a page without the button is a result of the case, with the page text beside it
                    out["refused"] = f"button {button!r} not pressed ({type(e).__name__}); page said: {text[:200]!r}"
        await b.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("button", nargs="?")
    ap.add_argument("--value")
    ap.add_argument("--own-host")
    a = ap.parse_args()
    for k, v in asyncio.run(act(a.url, a.button, a.value, a.own_host)).items():
        print(f"{k}: {v}")

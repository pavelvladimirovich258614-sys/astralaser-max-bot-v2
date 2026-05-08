import html
import re
import sys

import httpx

OG_IMAGE_RE = re.compile(
    r'<meta\s+(?=[^>]*\bproperty=["\']og:image["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
    re.IGNORECASE,
)


def resolve_ibb_urls(urls: list[str]) -> int:
    if not urls:
        print("Usage: python scripts/resolve_ibb.py https://ibb.co/...")
        return 1

    with httpx.Client(timeout=30.0, follow_redirects=True, trust_env=False) as client:
        for short_url in urls:
            response = client.get(short_url)
            if response.status_code == 404:
                print(f"{short_url} -> 404")
                continue

            response.raise_for_status()
            match = OG_IMAGE_RE.search(response.text)
            if not match:
                print(f"{short_url} -> og:image not found")
                continue

            direct_url = html.unescape(match.group(1))
            print(f"{short_url} -> {direct_url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(resolve_ibb_urls(sys.argv[1:]))


import re
import requests
from urllib.parse import urlsplit, urlunsplit, parse_qs, unquote

TEMPLATE_URL = (
    "https://raw.githubusercontent.com/fark19/keki/"
    "refs/heads/main/0A.m3u"
)

MAHSUN_URL = (
    "https://raw.githubusercontent.com/kadirsener1/mahsun/"
    "refs/heads/main/mahsun.m3u"
)

ATOM_URL = (
    "https://raw.githubusercontent.com/kadirsener1/atom/"
    "refs/heads/main/playlist.m3u"
)

OUTPUT_FILE = "0A.m3u"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Fallback referers used if no valid referer is found.
FALLBACK_MAHSUN_REFERER = "https://mahsunsports14.xyz/"
FALLBACK_ATOM_REFERER = "none"


def fetch_text(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def get_first_referer_and_domain(playlist, fallback_referer):
    """
    Extract the first valid referer and its associated stream domain.

    Supports proxy URLs such as:
    https://proxy.example/?url=https://stream.example/channel.m3u8

    If no referer is found, fallback_referer is used.
    """
    lines = playlist.splitlines()

    referer_pattern = re.compile(
        r'\b(?:http[-_])?referr?er\s*=\s*'
        r'(?:"([^"]*)"|\'([^\']*)\'|([^,\s]+))',
        re.IGNORECASE,
    )

    first_referer = None
    first_domain = None

    for i, line in enumerate(lines):
        # Find the first valid referer.
        match = referer_pattern.search(line)

        if match and first_referer is None:
            value = next(
                (v for v in match.groups() if v is not None),
                None,
            )

            if value and value.strip().lower() not in ("none", "null", ""):
                first_referer = value.strip()

        # Ignore M3U metadata and blank lines when finding URLs.
        candidate = line.strip()

        if not candidate.startswith(("http://", "https://")):
            continue

        parsed = urlsplit(candidate)

        # Extract the real stream URL from proxy query parameter ?url=
        query = parse_qs(parsed.query)

        if query.get("url"):
            stream_url = unquote(query["url"][0])
        else:
            stream_url = candidate

        stream = urlsplit(stream_url)

        if stream.scheme.lower() in ("http", "https") and stream.hostname:
            if first_domain is None:
                first_domain = stream.netloc

        if first_referer and first_domain:
            break

    if not first_domain:
        raise ValueError("No valid stream domain found in source playlist.")

    if not first_referer:
        first_referer = fallback_referer
        print(f"No referer found; using fallback: {first_referer}")

    return first_referer, first_domain


def replace_referer(line, referer):
    """Replace or add the referer attribute in an EXTINF line."""
    pattern = (
        r'(\breferer\s*=\s*)"[^"]*"'
        r'|(\breferer\s*=\s*)[^,\s]+'
    )

    if re.search(pattern, line, re.IGNORECASE):
        return re.sub(
            pattern,
            lambda m: (m.group(1) or m.group(2)) + f'"{referer}"',
            line,
            count=1,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r'(#EXTINF:[^,]*)',
        lambda m: m.group(1) + f' referer="{referer}"',
        line,
        count=1,
    )


def replace_domain(url, domain):
    """Replace the hostname while preserving the URL path and query."""
    parsed = urlsplit(url)

    return urlunsplit((
        parsed.scheme,
        domain,
        parsed.path,
        parsed.query,
        parsed.fragment,
    ))


def main():
    template = fetch_text(TEMPLATE_URL)
    mahsun = fetch_text(MAHSUN_URL)
    atom = fetch_text(ATOM_URL)

    # Extract referers and domains independently for both groups.
    mahsun_referer, mahsun_domain = get_first_referer_and_domain(
        mahsun,
        FALLBACK_MAHSUN_REFERER,
    )

    atom_referer, atom_domain = get_first_referer_and_domain(
        atom,
        FALLBACK_ATOM_REFERER,
    )

    print("Bölüm-1 referer:", mahsun_referer)
    print("Bölüm-1 domain:", mahsun_domain)
    print("Bölüm-2 referer:", atom_referer)
    print("Bölüm-2 domain:", atom_domain)

    lines = template.splitlines()
    current_group = None
    updated = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("#EXTINF:"):
            group_match = re.search(
                r'\bgroup-title="([^"]*)"',
                line,
                re.IGNORECASE,
            )

            current_group = (
                group_match.group(1) if group_match else None
            )

            if current_group == "bölüm-1":
                line = replace_referer(line, mahsun_referer)

            elif current_group == "bölüm-2":
                line = replace_referer(line, atom_referer)

            updated.append(line)
            continue

        if stripped.startswith(("http://", "https://")):
            if current_group == "bölüm-1":
                if "/checklist/androstreamlivebs" in stripped:
                    line = replace_domain(stripped, mahsun_domain)

            elif current_group == "bölüm-2":
                if "/tracks-v1a1/mono.m3u8" in stripped:
                    parsed = urlsplit(stripped)

                    # Keep the desired /beintv/ path.
                    path = re.sub(
                        r"/bein\d*/tracks-v1a1/mono\.m3u8$",
                        "/beintv/tracks-v1a1/mono.m3u8",
                        parsed.path,
                        flags=re.IGNORECASE,
                    )

                    line = urlunsplit((
                        parsed.scheme,
                        atom_domain,
                        path,
                        parsed.query,
                        parsed.fragment,
                    ))

        updated.append(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(updated) + "\n")

    print(f"Successfully updated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

import re
import requests
from urllib.parse import urlsplit, urlunsplit

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
    "refs/heads/main/atom.m3u"
)

OUTPUT_FILE = "0A.m3u"

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_text(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def get_first_referer_and_domain(playlist):
    lines = playlist.splitlines()

    # Match referer/referrer attributes, quoted or unquoted.
    referer_pattern = re.compile(
        r'\b(?:http[-_])?referr?er\s*=\s*'
        r'(?:"([^"]*)"|\'([^\']*)\'|([^,\s]+))',
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        match = referer_pattern.search(line)

        if not match:
            continue

        referer = next(
            (value for value in match.groups() if value is not None),
            None,
        )

        if not referer or referer.lower() in ("none", "null"):
            continue

        # Find the stream URL associated with this entry.
        for next_line in lines[i + 1:]:
            candidate = next_line.strip()

            if not candidate:
                continue

            # Do not cross into another channel entry.
            if candidate.startswith("#EXTINF:"):
                break

            if candidate.startswith("#"):
                continue

            parsed = urlsplit(candidate)

            if parsed.scheme.lower() in ("http", "https") and parsed.hostname:
                return referer, parsed.netloc

            # Stop if this is not a valid stream URL.
            break

    # Print useful diagnostic information if no matching pair exists.
    print("DEBUG: No valid referer/domain pair found.")
    print("DEBUG: First playlist lines:")
    for line in lines[:20]:
        print(repr(line))

    raise ValueError(
        "Could not find a valid referer and associated stream URL. "
        "Check the DEBUG output above."
    )


def replace_referer(line, referer):
    """Replace the referer attribute, preserving other attributes."""
    if re.search(r'\breferer\s*=', line, re.IGNORECASE):
        return re.sub(
            r'(\breferer\s*=\s*)"[^"]*"|'
            r"(\breferer\s*=\s*)[^,\s]+",
            lambda m: (
                (m.group(1) or m.group(2))
                + '"'
                + referer
                + '"'
            ),
            line,
            count=1,
            flags=re.IGNORECASE,
        )

    # Add the attribute if it does not exist.
    return re.sub(
        r'(#EXTINF:[^,]*)',
        lambda m: m.group(1) + f' referer="{referer}"',
        line,
        count=1,
    )


def replace_domain(url, domain):
    """Replace only the URL hostname, preserving path and query."""
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

    # Get each playlist's first referer and associated stream domain.
    mahsun_referer, mahsun_domain = get_first_referer_and_domain(mahsun)
    atom_referer, atom_domain = get_first_referer_and_domain(atom)

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

        if stripped.startswith("http://") or stripped.startswith("https://"):
            if current_group == "bölüm-1":
                if "/checklist/androstream" in stripped:
                    line = replace_domain(stripped, mahsun_domain)

            elif current_group == "bölüm-2":
                if "/tracks-v1a1/mono.m3u8" in stripped:
                    parsed = urlsplit(stripped)

                    # Replace the channel path with /beintv/.
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

    print(f"Updated playlist saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

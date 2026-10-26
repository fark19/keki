
import re
import requests
from urllib.parse import urlsplit, parse_qs, unquote

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

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Fallback referer used only when bölüm-1 has no valid source referer.
FALLBACK_MAHSUN_REFERER = "https://mahsunsports14.xyz/"


def fetch_text(url):
    """Download a text playlist."""
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def extract_referer(playlist, fallback):
    """
    Return the first valid referer found in the source playlist.
    Use fallback if no valid referer is available.
    """
    pattern = re.compile(
        r'\b(?:http[-_])?referr?er\s*=\s*'
        r'(?:"([^"]*)"|\'([^\']*)\'|([^,\s]+))',
        re.IGNORECASE,
    )

    for line in playlist.splitlines():
        match = pattern.search(line)

        if not match:
            continue

        value = next(
            (v for v in match.groups() if v is not None),
            "",
        ).strip()

        if value and value.lower() not in ("none", "null"):
            return value

    print(f"No valid referer found; using fallback: {fallback}")
    return fallback


def extract_stream_domain(playlist):
    """
    Extract the hostname from the first valid stream URL.

    Supports direct URLs and proxy URLs such as:
    https://proxy.example/?url=https://stream.example/channel.m3u8
    """
    for line in playlist.splitlines():
        candidate = line.strip()

        if not candidate.startswith(("http://", "https://")):
            continue

        parsed = urlsplit(candidate)
        query = parse_qs(parsed.query)

        if query.get("url"):
            stream_url = unquote(query["url"][0]).strip()
        else:
            stream_url = candidate

        stream = urlsplit(stream_url)

        if (
            stream.scheme.lower() in ("http", "https")
            and stream.hostname
            and stream.netloc
        ):
            return stream.netloc

    raise ValueError(
        "Could not find a valid stream domain in source playlist."
    )


def replace_referer(line, referer):
    """Replace or add a referer attribute on an EXTINF line."""
    pattern = (
        r'\breferer\s*=\s*'
        r'(?:"[^"]*"|\'[^\']*\'|[^,\s]*)'
    )

    if re.search(pattern, line, re.IGNORECASE):
        return re.sub(
            pattern,
            lambda _: f'referer="{referer}"',
            line,
            count=1,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r'(#EXTINF:[^,]*)',
        lambda match: (
            match.group(1) + f' referer="{referer}"'
        ),
        line,
        count=1,
    )


def replace_url_domain(url, domain):
    """Replace the hostname and preserve the rest of the URL."""
    parsed = urlsplit(url.strip())

    return parsed._replace(netloc=domain).geturl()


def main():
    print("Downloading playlists...")

    template = fetch_text(TEMPLATE_URL)
    mahsun = fetch_text(MAHSUN_URL)
    atom = fetch_text(ATOM_URL)

    # bölüm-1: get referer and stream domain from mahsun.m3u.
    mahsun_referer = extract_referer(
        mahsun,
        FALLBACK_MAHSUN_REFERER,
    )
    mahsun_domain = extract_stream_domain(mahsun)

    # bölüm-2: get the actual stream domain from atom.m3u.
    # Its referer will always be "none".
    atom_domain = extract_stream_domain(atom)

    print("bölüm-1 referer:", mahsun_referer)
    print("bölüm-1 domain:", mahsun_domain)
    print("bölüm-2 referer: none")
    print("bölüm-2 domain:", atom_domain)

    lines = template.splitlines()
    output = []
    current_group = None

    for line in lines:
        stripped = line.strip()

        # Identify the group for each channel.
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
                line = replace_referer(
                    line,
                    mahsun_referer,
                )

            elif current_group == "bölüm-2":
                line = replace_referer(
                    line,
                    "none",
                )

            output.append(line)
            continue

        # Update stream URLs according to the current group.
        if stripped.startswith(("http://", "https://")):

            if current_group == "bölüm-1":
                if "/checklist/androstreamlivebs" in stripped:
                    line = replace_url_domain(
                        stripped,
                        mahsun_domain,
                    )

            elif current_group == "bölüm-2":
                # Change only the hostname.
                # Preserve every original channel path, such as:
                # //beintv/tracks-v1a1/mono.m3u8
                # //bein1/tracks-v1a1/mono.m3u8
                # //s-sport2/tracks-v1a1/mono.m3u8
                # //trt-spor/tracks-v1a1/mono.m3u8
                line = replace_url_domain(
                    stripped,
                    atom_domain,
                )

        output.append(line)

    # Save the updated playlist.
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write("\n".join(output) + "\n")

    print(f"Successfully generated {OUTPUT_FILE}")
    print("All existing channels have been preserved.")


if __name__ == "__main__":
    main()

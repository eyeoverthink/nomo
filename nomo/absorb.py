"""Fetch one public page into a vault note.

Private hosts, link-local addresses, and non-web schemes are refused.
The fetch is operator-started or a model tool with the same check.
"""

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

from nomo import vault

_BLOCKED = {"localhost", "metadata.google.internal"}
_MAX_BYTES = 400_000


def public_target(url):
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only an http or https URL can be absorbed.")
    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("That host is not a public page.")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("That host did not resolve.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError("That host is not a public page.")
    return url.strip()


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_target(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _text(raw, content_type):
    if "html" in content_type:
        lowered = raw.lower()
        for tag in ("script", "style"):
            start = lowered.find("<%s" % tag)
            while start >= 0:
                end = lowered.find("</%s>" % tag, start)
                if end < 0:
                    raw = raw[:start]
                    lowered = raw.lower()
                    break
                raw = raw[:start] + " " + raw[end + 3 + len(tag) :]
                lowered = raw.lower()
                start = lowered.find("<%s" % tag)
        out = []
        skip = False
        for char in raw:
            if char == "<":
                skip = True
            elif char == ">":
                skip = False
                out.append(" ")
            elif not skip:
                out.append(char)
        return " ".join("".join(out).split())
    return raw.strip()


def fetch(url):
    target = public_target(url)
    opener = urllib.request.build_opener(_Redirect)
    request = urllib.request.Request(target, headers={"User-Agent": "nomo-absorb"})
    try:
        with opener.open(request, timeout=20) as response:
            public_target(response.geturl())
            content_type = (response.headers.get("Content-Type") or "").lower()
            payload = response.read(_MAX_BYTES + 1)
    except urllib.error.URLError as exc:
        raise ValueError("The page could not be fetched (%s)." % exc.reason) from exc
    if len(payload) > _MAX_BYTES:
        payload = payload[:_MAX_BYTES]
    text = _text(payload.decode("utf-8", errors="replace"), content_type)
    if not text:
        raise ValueError("The page had no text.")
    slug = urllib.parse.urlparse(target).hostname.replace(".", "-")
    name = "notes/absorb-%s.md" % slug
    body = "# %s\n\nSource: %s\n\n%s\n" % (slug, target, text[:8000])
    saved = vault.write(name, body)
    return {"note": saved, "chars": len(text)}

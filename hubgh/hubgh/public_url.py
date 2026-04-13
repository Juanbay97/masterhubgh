from contextlib import contextmanager
from urllib.parse import urljoin, urlsplit, urlunsplit

import frappe


PUBLIC_BASE_URL_KEYS = (
	"hubgh_public_base_url",
	"hubgh_canonical_base_url",
	"public_base_url",
	"canonical_base_url",
)


def get_public_base_url():
	for key in PUBLIC_BASE_URL_KEYS:
		value = _normalize_base_url(_conf_get(frappe.conf, key))
		if value:
			return value

	return _normalize_base_url(_conf_get(frappe.conf, "host_name"))


def build_public_url(url=None):
	base_url = get_public_base_url()
	if not url:
		return base_url or ""
	if not base_url:
		return url

	parsed = urlsplit(str(url).strip())
	if parsed.scheme and parsed.netloc:
		relative_url = urlunsplit(("", "", parsed.path or "/", parsed.query, parsed.fragment))
		return urljoin(f"{base_url}/", relative_url.lstrip("/"))

	return urljoin(f"{base_url}/", str(url).lstrip("/"))


@contextmanager
def override_public_base_url_for_frappe():
	base_url = get_public_base_url()
	if not base_url:
		yield None
		return

	targets = _get_conf_targets()
	previous_values = []

	for conf in targets:
		previous_values.append((conf, _conf_has(conf, "host_name"), _conf_get(conf, "host_name")))
		_conf_set(conf, "host_name", base_url)

	try:
		yield base_url
	finally:
		for conf, had_value, previous_value in previous_values:
			if had_value:
				_conf_set(conf, "host_name", previous_value)
			else:
				_conf_delete(conf, "host_name")


def _normalize_base_url(value):
	text = (value or "").strip()
	if not text:
		return ""
	if "://" not in text:
		text = f"https://{text}"
	return text.rstrip("/")


def _get_conf_targets():
	targets = []
	seen = set()
	for conf in (getattr(frappe, "conf", None), getattr(getattr(frappe, "local", None), "conf", None)):
		if conf is None or id(conf) in seen:
			continue
		seen.add(id(conf))
		targets.append(conf)
	return targets


def _conf_get(conf, key):
	if conf is None:
		return None
	if hasattr(conf, "get"):
		return conf.get(key)
	return getattr(conf, key, None)


def _conf_has(conf, key):
	if conf is None:
		return False
	if hasattr(conf, "keys"):
		return key in conf
	return hasattr(conf, key)


def _conf_set(conf, key, value):
	if conf is None:
		return
	if hasattr(conf, "__setitem__"):
		conf[key] = value
		return
	setattr(conf, key, value)


def _conf_delete(conf, key):
	if conf is None:
		return
	if hasattr(conf, "pop"):
		conf.pop(key, None)
		return
	if hasattr(conf, "__delitem__"):
		try:
			del conf[key]
			return
		except Exception:
			pass
	if hasattr(conf, key):
		setattr(conf, key, None)

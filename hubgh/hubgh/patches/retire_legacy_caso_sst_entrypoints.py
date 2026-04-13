import json

import frappe


def execute():
	if not frappe.db.exists("Workspace", "SST"):
		return

	workspace = frappe.get_doc("Workspace", "SST")
	updated_shortcuts = [
		row
		for row in (workspace.shortcuts or [])
		if not (getattr(row, "type", None) == "DocType" and getattr(row, "link_to", None) == "Caso SST")
	]

	content = _filter_workspace_content(workspace.content)
	content_changed = content != (workspace.content or "")
	shortcuts_changed = len(updated_shortcuts) != len(workspace.shortcuts or [])

	if not content_changed and not shortcuts_changed:
		return

	workspace.set("shortcuts", updated_shortcuts)
	workspace.content = content
	workspace.save(ignore_permissions=True)


def _filter_workspace_content(raw_content):
	if not raw_content:
		return raw_content

	try:
		blocks = json.loads(raw_content)
	except Exception:
		return raw_content

	filtered = []
	for block in blocks:
		shortcut_name = ((block or {}).get("data") or {}).get("shortcut_name")
		if shortcut_name == "Casos SST":
			continue
		filtered.append(block)

	return json.dumps(filtered, ensure_ascii=False, separators=(",", ":"))

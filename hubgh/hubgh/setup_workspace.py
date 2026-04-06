
import frappe

def setup_workspace():
    # 1. Crear Workspace "HubGH"
    if not frappe.db.exists("Workspace", "HubGH"):
        doc = frappe.new_doc("Workspace")
        doc.label = "HubGH"
        doc.name = "HubGH"
        doc.public = 1
        doc.is_standard = 0
        doc.module = "Hubgh"
        doc.icon = "users"
        doc.sequence_id = 1
        doc.append("shortcuts", {
            "type": "Page",
            "label": "Punto 360",
            "link_to": "punto_360",
            "color": "Green"
        })
        doc.insert(ignore_permissions=True)
        print("Workspace 'HubGH' created with shortcut.")
    else:
        print("Workspace 'HubGH' already exists.")
        
    frappe.db.commit()

setup_workspace()

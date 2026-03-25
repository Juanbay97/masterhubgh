
import frappe
import json

def add_shortcut():
    try:
        # Check if 'Home' workspace exists, or get the default one
        workspace = frappe.get_doc("Workspace", "Home")
        
        # Check if shortcut already exists to avoid duplication
        exists = any(s.label == "Punto 360" for s in workspace.shortcuts)
        
        if not exists:
            workspace.append("shortcuts", {
                "type": "Page",
                "label": "Punto 360",
                "link_to": "punto_360",
                "color": "Green"
            })
            workspace.save()
            frappe.db.commit()
            print("Shortcut added successfully to Home.")
        else:
            print("Shortcut already exists.")
            
    except Exception as e:
        print(f"Error adding shortcut: {str(e)}")

add_shortcut()

import frappe
from frappe.utils import get_site_path

from hubgh.hubgh.role_matrix import get_transitional_roles

def setup_roles():
    roles = [
        "Gestión Humana",
        "HR Selection",
        "HR Labor Relations",
        "HR SST",
        "HR Training & Wellbeing",
        "Jefe_PDV",
        "Empleado",
        "GH - Bandeja General",
        "GH - SST",
        "GH - RRLL",
    ]
    for role in roles:
        if not frappe.db.exists("Role", role):
            doc = frappe.new_doc("Role")
            doc.role_name = role
            doc.desk_access = 1
            doc.save(ignore_permissions=True)
            print(f"Created Role: {role}")
        else:
            print(f"Role exists: {role}")

def setup_workspaces():
    workspaces = [
        {
            "name": "GH",
            "title": "Gestión Humana",
            "icon": "users",
            "roles": get_transitional_roles(["Gestión Humana"]),
            "sequence_id": 1,
            "public": 1,
            "module": "Hubgh"
        },
        {
            "name": "Operación",
            "title": "Operación",
            "icon": "activity",
            "roles": get_transitional_roles(["Jefe_PDV", "Gestión Humana"]),
            "sequence_id": 2,
            "public": 1,
            "module": "Hubgh"
        },
        {
            "name": "Mi perfil",
            "title": "Mi Perfil",
            "icon": "user",
            "roles": get_transitional_roles(["Empleado", "Gestión Humana", "Jefe_PDV"]),
            "sequence_id": 3,
            "public": 1,
            "module": "Hubgh"
        }
    ]

    for ws_data in workspaces:
        ws_name = ws_data["name"]
        
        # Check if workspace exists
        if frappe.db.exists("Workspace", ws_name):
            doc = frappe.get_doc("Workspace", ws_name)
        else:
            doc = frappe.new_doc("Workspace")
            doc.name = ws_name
            doc.label = ws_data["title"] # Label is used for title
            doc.title = ws_data["title"] 

        doc.module = ws_data.get("module", "Hubgh")
        doc.icon = ws_data.get("icon", "folder")
        doc.public = 1
        doc.sequence_id = ws_data.get("sequence_id", 1)
        
        # Clear existing roles and add new ones
        doc.roles = []
        for role in ws_data["roles"]:
            doc.append("roles", {"role": role})
            
        doc.save(ignore_permissions=True)
        print(f"Setup Workspace: {ws_name}")

def setup_branding():
    # Update Website Settings
    web_settings = frappe.get_doc("Website Settings")
    web_settings.app_name = "Home Intranet"
    web_settings.app_logo = "/assets/hubgh/images/logo-dark.png"
    web_settings.banner_image = "/assets/hubgh/images/logo-white.png"     
    web_settings.brand_html = "<img src='/assets/hubgh/images/logo-white.png' style='max-width: 40px; max-height: 40px;'>"
    web_settings.save(ignore_permissions=True)
    
    # Update System Settings (optional but good for desk)
    sys_settings = frappe.get_single("System Settings")
    sys_settings.app_name = "Home Intranet"
    sys_settings.save(ignore_permissions=True)

    print("Branding Applied")

def cleanup_workspaces():
    # List of standard workspaces to hide/restrict
    standard_workspaces = [
        "Build", "Settings", "Users", "Integrations", "Getting Started", "Tools", "Website", "ERPNext"
    ]
    
    for ws_name in standard_workspaces:
        if frappe.db.exists("Workspace", ws_name):
            doc = frappe.get_doc("Workspace", ws_name)
            # Make private or restrict to System Manager
            # Making private is safer as it hides it from Sidebar for everyone except owners/admins who explicitly look for it
            # Or better, restricting to System Manager
            
            # Reset roles to only System Manager
            doc.roles = []
            doc.append("roles", {"role": "System Manager"})
            doc.public = 0 # Consider making them non-public or just restricted
            # Actually, keeping public=1 but restricting roles is standard for "Restricted" workspaces
            # But standard workspaces often have default public behavior. 
            # Let's set roles to System Manager.
            
            doc.save(ignore_permissions=True)
            print(f"Restricted Workspace: {ws_name} to System Manager")

def run():
    setup_roles()
    setup_workspaces()
    setup_branding()
    cleanup_workspaces()
    frappe.db.commit()

if __name__ == "__main__":
    run()

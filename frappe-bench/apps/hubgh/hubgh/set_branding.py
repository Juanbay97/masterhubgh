import frappe
import shutil
import os

def set_branding():
    # 1. Move logo to public folder
    source = "/home/frappe/.gemini/antigravity/brain/3759acce-dcf1-4981-a581-3ce6aceabde0/hubgh_logo_1768858390734.png"
    dest_dir = frappe.get_site_path("public", "files")
    file_name = "hubgh_logo.png"
    dest_path = os.path.join(dest_dir, file_name)
    
    # Ensure directory
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    shutil.copy(source, dest_path)
    file_url = f"/files/{file_name}"
    print(f"Logo moved to {dest_path}")
    
    # 2. Update Website Settings
    ws = frappe.get_doc("Website Settings")
    ws.app_logo = file_url
    ws.app_name = "HubGH"
    ws.banner_image = file_url
    ws.brand_html = f"<img src='{file_url}' style='height: 30px;'>"
    ws.save()
    print("Website Settings updated with new Logo")

    # 3. Update Navbar Settings (Top bar)
    ns = frappe.get_doc("Navbar Settings")
    ns.app_logo = file_url
    ns.save()
    print("Navbar Settings updated")
    
    frappe.db.commit()

if __name__ == "__main__":
    frappe.init(site="hubgh.test")
    frappe.connect()
    set_branding()

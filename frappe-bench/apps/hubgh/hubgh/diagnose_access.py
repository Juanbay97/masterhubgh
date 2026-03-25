import frappe


def run(user="gh_user_test@example.com"):
    frappe.set_user("Administrator")
    admin_roles = set(frappe.get_roles("Administrator"))
    user_roles = set(frappe.get_roles(user))

    pages = ["punto_360", "persona_360", "centro_de_datos"]
    workspaces = ["Gestión Humana", "Operación", "Mi Perfil"]

    print("User:", user)
    print("User Roles:", sorted(user_roles))
    print("Admin Roles:", sorted(admin_roles))
    print("Missing vs Admin:", sorted(admin_roles - user_roles))

    print("\nPage role checks:")
    for p in pages:
        page = frappe.get_doc("Page", p)
        page_roles = {r.role for r in page.roles}
        print(p, "roles:", sorted(page_roles), "user_has_access:", bool(user_roles & page_roles))

    print("\nWorkspace role checks:")
    for w in workspaces:
        ws = frappe.get_doc("Workspace", w)
        ws_roles = {r.role for r in ws.roles}
        print(w, "roles:", sorted(ws_roles), "user_has_access:", bool(user_roles & ws_roles))

    print("\nDoctype read checks:")
    doctypes = ["Ficha Empleado", "Punto de Venta", "Novedad SST", "Caso SST", "Caso Disciplinario", "Feedback Punto"]
    for dt in doctypes:
        has_read = frappe.has_permission(dt, "read", user=user)
        print(dt, "read:", has_read)


def fix_access(user="gh_user_test@example.com"):
    frappe.set_user("Administrator")

    def clean_roles(role_rows):
        return [r for r in role_rows if frappe.db.exists("Role", r.role)]

    # Ensure page roles include Gestión Humana
    for page_name in ["punto_360", "persona_360"]:
        page = frappe.get_doc("Page", page_name)
        page.roles = clean_roles(page.roles)
        page_roles = {r.role for r in page.roles}
        if "Gestión Humana" not in page_roles:
            page.append("roles", {"role": "Gestión Humana"})
        page.save(ignore_permissions=True)

    # Ensure workspace roles use Gestión Humana (replace GH_Central)
    for ws_name in ["Gestión Humana", "Operación", "Mi Perfil"]:
        ws = frappe.get_doc("Workspace", ws_name)
        ws.roles = clean_roles(ws.roles)
        roles = [r.role for r in ws.roles]
        if "GH_Central" in roles:
            ws.roles = [r for r in ws.roles if r.role != "GH_Central"]
            if "Gestión Humana" not in [r.role for r in ws.roles]:
                ws.append("roles", {"role": "Gestión Humana"})
        ws.save(ignore_permissions=True)

    # Remove GH_Central role from user and ensure Gestión Humana
    user_doc = frappe.get_doc("User", user)
    if "GH_Central" in [r.role for r in user_doc.roles]:
        user_doc.remove_roles("GH_Central")
    if "Gestión Humana" not in [r.role for r in user_doc.roles]:
        user_doc.add_roles("Gestión Humana")
    user_doc.save(ignore_permissions=True)

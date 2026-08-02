import os
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, MODIFY_ADD, MODIFY_DELETE, HASHED_SALTED_SHA
from ldap3.utils.hashed import hashed
from fastmcp import FastMCP

mcp = FastMCP(
    "fuchs-ldap",
    instructions="OpenLDAP Nutzerverwaltung auf darwin26. Nutzer und Gruppen anlegen, bearbeiten, löschen. Base DN: dc=sternenhof,dc=space",
)

LDAP_URL    = os.environ.get("LDAP_URL", "ldap://localhost")
LDAP_BIND   = os.environ.get("LDAP_BIND_DN", "cn=admin,dc=sternenhof,dc=space")
LDAP_PASS   = os.environ["LDAP_PASSWORD"]
BASE_DN     = os.environ.get("LDAP_BASE_DN", "dc=sternenhof,dc=space")
USERS_DN    = f"ou=users,{BASE_DN}"
GROUPS_DN   = f"ou=groups,{BASE_DN}"


def get_conn() -> Connection:
    server = Server(LDAP_URL, get_info=ALL)
    conn = Connection(server, LDAP_BIND, LDAP_PASS, auto_bind=True)
    return conn


# ── NUTZER ────────────────────────────────────────────────────────────────────

@mcp.tool()
def ldap_list_users() -> list:
    """Alle LDAP-Nutzer auflisten."""
    with get_conn() as conn:
        conn.search(USERS_DN, "(objectClass=inetOrgPerson)",
                    attributes=["uid", "cn", "sn", "givenName", "mail", "memberOf"])
        return [
            {
                "dn": str(e.entry_dn),
                "uid": str(e.uid) if e.uid else "",
                "cn": str(e.cn) if e.cn else "",
                "givenName": str(e.givenName) if hasattr(e, "givenName") and e.givenName else "",
                "sn": str(e.sn) if e.sn else "",
                "mail": str(e.mail) if hasattr(e, "mail") and e.mail else "",
                "groups": [str(g) for g in e.memberOf] if hasattr(e, "memberOf") and e.memberOf else [],
            }
            for e in conn.entries
        ]

@mcp.tool()
def ldap_get_user(uid: str) -> dict:
    """LDAP-Nutzer anhand UID abrufen."""
    with get_conn() as conn:
        conn.search(USERS_DN, f"(uid={uid})",
                    attributes=["uid", "cn", "sn", "givenName", "mail", "telephoneNumber", "memberOf"])
        if not conn.entries:
            return {"error": f"Nutzer '{uid}' nicht gefunden"}
        e = conn.entries[0]
        return {
            "dn": str(e.entry_dn),
            "uid": str(e.uid),
            "cn": str(e.cn),
            "givenName": str(e.givenName) if hasattr(e, "givenName") and e.givenName else "",
            "sn": str(e.sn),
            "mail": str(e.mail) if hasattr(e, "mail") and e.mail else "",
            "phone": str(e.telephoneNumber) if hasattr(e, "telephoneNumber") and e.telephoneNumber else "",
            "groups": [str(g) for g in e.memberOf] if hasattr(e, "memberOf") and e.memberOf else [],
        }

@mcp.tool()
def ldap_create_user(uid: str, first_name: str, last_name: str, password: str, mail: str = "") -> dict:
    """Neuen LDAP-Nutzer anlegen. Wird sofort in allen angebundenen Diensten verfügbar (Nextcloud, Jellyfin, Immich)."""
    dn = f"uid={uid},{USERS_DN}"
    attrs = {
        "objectClass": ["inetOrgPerson", "organizationalPerson", "person", "top"],
        "uid": uid,
        "cn": f"{first_name} {last_name}",
        "givenName": first_name,
        "sn": last_name,
        "userPassword": hashed(HASHED_SALTED_SHA, password),
    }
    if mail:
        attrs["mail"] = mail
    with get_conn() as conn:
        success = conn.add(dn, attributes=attrs)
        if success:
            return {"success": True, "dn": dn}
        return {"error": conn.result["description"], "detail": conn.result}

@mcp.tool()
def ldap_update_user(uid: str, first_name: str = "", last_name: str = "", mail: str = "", phone: str = "") -> dict:
    """LDAP-Nutzer aktualisieren."""
    dn = f"uid={uid},{USERS_DN}"
    changes: dict = {}
    if first_name: changes["givenName"] = [(MODIFY_REPLACE, [first_name])]
    if last_name:  changes["sn"]        = [(MODIFY_REPLACE, [last_name])]
    if mail:       changes["mail"]      = [(MODIFY_REPLACE, [mail])]
    if phone:      changes["telephoneNumber"] = [(MODIFY_REPLACE, [phone])]
    if first_name or last_name:
        fn = first_name or uid
        ln = last_name or ""
        changes["cn"] = [(MODIFY_REPLACE, [f"{fn} {ln}".strip()])]
    with get_conn() as conn:
        success = conn.modify(dn, changes)
        if success:
            return {"success": True}
        return {"error": conn.result["description"]}

@mcp.tool()
def ldap_reset_password(uid: str, new_password: str) -> dict:
    """Passwort eines Nutzers zurücksetzen."""
    dn = f"uid={uid},{USERS_DN}"
    with get_conn() as conn:
        success = conn.modify(dn, {"userPassword": [(MODIFY_REPLACE, [hashed(HASHED_SALTED_SHA, new_password)])]})
        if success:
            return {"success": True}
        return {"error": conn.result["description"]}

@mcp.tool()
def ldap_delete_user(uid: str) -> dict:
    """LDAP-Nutzer löschen."""
    dn = f"uid={uid},{USERS_DN}"
    with get_conn() as conn:
        success = conn.delete(dn)
        if success:
            return {"success": True}
        return {"error": conn.result["description"]}


# ── GRUPPEN ───────────────────────────────────────────────────────────────────

@mcp.tool()
def ldap_list_groups() -> list:
    """Alle LDAP-Gruppen auflisten."""
    with get_conn() as conn:
        conn.search(GROUPS_DN, "(objectClass=groupOfNames)",
                    attributes=["cn", "description", "member"])
        return [
            {
                "dn": str(e.entry_dn),
                "cn": str(e.cn),
                "description": str(e.description) if hasattr(e, "description") and e.description else "",
                "memberCount": len(e.member) if hasattr(e, "member") and e.member else 0,
                "members": [str(m) for m in e.member] if hasattr(e, "member") and e.member else [],
            }
            for e in conn.entries
        ]

@mcp.tool()
def ldap_add_user_to_group(uid: str, group_cn: str) -> dict:
    """Nutzer zu einer Gruppe hinzufügen."""
    user_dn  = f"uid={uid},{USERS_DN}"
    group_dn = f"cn={group_cn},{GROUPS_DN}"
    with get_conn() as conn:
        success = conn.modify(group_dn, {"member": [(MODIFY_ADD, [user_dn])]})
        if success:
            return {"success": True}
        return {"error": conn.result["description"]}

@mcp.tool()
def ldap_remove_user_from_group(uid: str, group_cn: str) -> dict:
    """Nutzer aus einer Gruppe entfernen."""
    user_dn  = f"uid={uid},{USERS_DN}"
    group_dn = f"cn={group_cn},{GROUPS_DN}"
    with get_conn() as conn:
        success = conn.modify(group_dn, {"member": [(MODIFY_DELETE, [user_dn])]})
        if success:
            return {"success": True}
        return {"error": conn.result["description"]}

@mcp.tool()
def ldap_create_group(group_cn: str, description: str = "") -> dict:
    """Neue LDAP-Gruppe anlegen."""
    dn = f"cn={group_cn},{GROUPS_DN}"
    attrs = {
        "objectClass": ["groupOfNames", "top"],
        "cn": group_cn,
        "member": [LDAP_BIND],
    }
    if description:
        attrs["description"] = description
    with get_conn() as conn:
        success = conn.add(dn, attributes=attrs)
        if success:
            return {"success": True, "dn": dn}
        return {"error": conn.result["description"]}


if __name__ == "__main__":
    mcp.run()

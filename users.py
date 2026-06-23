"""
users.py
User management — Finance/Admin can view, edit, and delete company users.
"""

import streamlit as st
import database as db

ROLE_LABELS = {
    "reviewer":     "Reviewer",
    "manager":      "Manager",
    "finance/admin":"Finance / Admin",
}


def users_page():

    st.header("👥 User Management")

    if st.session_state.user["role"].lower() != "finance/admin":
        st.error("Only Finance / Admin users can access this page.")
        return

    company_id      = st.session_state.user["company_id"]
    current_user_id = st.session_state.user["id"]
    users           = db.get_company_users(company_id)

    if users.empty:
        st.info("No users found.")
        return

    # ── User table ────────────────────────────────────────────────────────────
    st.subheader("Company Users")
    st.caption("Click a row's action buttons to edit or remove that user.")

    display = users.copy()
    display["role"] = display["role"].map(ROLE_LABELS).fillna(display["role"])
    st.dataframe(
        display[["full_name", "email", "role"]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ── Select user to manage ─────────────────────────────────────────────────
    user_options = {
        row["id"]: f"{row['full_name']} ({row['email']})"
        for _, row in users.iterrows()
    }
    selected_id = st.selectbox(
        "Select user to manage",
        options=list(user_options.keys()),
        format_func=lambda uid: user_options[uid],
    )

    selected = users[users["id"] == selected_id].iloc[0]
    is_self  = int(selected_id) == int(current_user_id)

    tab_edit, tab_role, tab_delete = st.tabs([
        "✏️ Edit details", "🔄 Change role", "🗑️ Delete user"
    ])

    # ── Tab 1: Edit name and email ────────────────────────────────────────────
    with tab_edit:
        st.caption("Update the selected user's name or email address.")
        with st.form("edit_user_form"):
            new_name  = st.text_input("Full name",      value=selected["full_name"])
            new_email = st.text_input("Email address",  value=selected["email"])
            save = st.form_submit_button("Save changes", use_container_width=True)

            if save:
                if not new_name.strip():
                    st.error("Name cannot be empty.")
                elif not new_email.strip():
                    st.error("Email cannot be empty.")
                else:
                    ok, msg = db.update_user_details(selected_id, new_name, new_email)
                    if ok:
                        st.success(msg)
                        # If the logged-in user edited their own details, update session
                        if is_self:
                            st.session_state.user["full_name"] = new_name.strip()
                            st.session_state.user["email"]     = new_email.strip()
                        st.rerun()
                    else:
                        st.error(msg)

    # ── Tab 2: Change role ────────────────────────────────────────────────────
    with tab_role:
        st.caption("Change which approval role this user holds.")
        with st.form("role_form"):
            current_role_idx = list(ROLE_LABELS.keys()).index(selected["role"]) \
                               if selected["role"] in ROLE_LABELS else 0
            new_role = st.selectbox(
                "New role",
                options=list(ROLE_LABELS.keys()),
                index=current_role_idx,
                format_func=lambda r: ROLE_LABELS[r],
            )
            update = st.form_submit_button("Update role", use_container_width=True)

            if update:
                if is_self and new_role != "finance/admin":
                    st.error(
                        "You cannot remove your own Finance/Admin role — "
                        "you would lose access to this page."
                    )
                else:
                    db.update_user_role(selected_id, new_role)
                    st.success(
                        f"Role updated to {ROLE_LABELS[new_role]} for {selected['full_name']}."
                    )
                    st.rerun()

    # ── Tab 3: Delete user ────────────────────────────────────────────────────
    with tab_delete:
        if is_self:
            st.warning("You cannot delete your own account.")
        else:
            st.caption(
                f"This will permanently remove **{selected['full_name']}** "
                f"from the system. Their uploaded documents will remain."
            )
            confirm = st.checkbox(
                f"I confirm I want to delete {selected['full_name']}"
            )
            if st.button(
                "🗑️ Delete user permanently",
                disabled=not confirm,
                use_container_width=True,
            ):
                ok, msg = db.delete_user(selected_id, current_user_id)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

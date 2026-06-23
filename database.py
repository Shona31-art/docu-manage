import hashlib
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH="documanage.db"

def get_connection():

    conn=sqlite3.connect(DB_PATH)

    conn.row_factory=sqlite3.Row

    return conn

def calculate_file_hash(uploaded_file):

    uploaded_file.seek(0)

    file_hash=hashlib.sha256(
        uploaded_file.read()
    ).hexdigest()

    uploaded_file.seek(0)

    return file_hash

def init_db():

    conn=get_connection()
    cur=conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT UNIQUE,

    created_at TEXT

    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password_hash TEXT,
    full_name TEXT,
    role TEXT CHECK(role IN ('reviewer','manager','finance/admin')),
    company_id INTEGER,
    created_at TEXT,
    FOREIGN KEY(company_id)
    REFERENCES companies(id)
    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT,
    file_path TEXT,
    file_hash TEXT,
    document_type TEXT,
    vendor_name TEXT,
    invoice_number TEXT,
    invoice_date TEXT,
    subtotal REAL,
    vat_amount REAL,
    amount REAL,
    status TEXT DEFAULT 'pending',
    is_duplicate INTEGER DEFAULT 0,
    uploaded_by INTEGER,
    company_id INTEGER,
    created_at TEXT,
    FOREIGN KEY(uploaded_by)
    REFERENCES users(id),
    FOREIGN KEY(company_id)
    REFERENCES companies(id)
    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS approvals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    step INTEGER,
    role_required TEXT,
    status TEXT DEFAULT 'pending',
    approver_id INTEGER,
    comments TEXT,
    actioned_at TEXT,
    FOREIGN KEY(document_id)
    REFERENCES documents(id)
    )
    """)

    # Migration: add company_id to documents if upgrading an older database
    # that was created before company support existed. Must run AFTER the
    # CREATE TABLE statements above, since this checks an existing table.
    cur.execute("PRAGMA table_info(documents)")
    columns=[row[1] for row in cur.fetchall()]

    if "company_id" not in columns:
        cur.execute("""
        ALTER TABLE documents
        ADD COLUMN company_id INTEGER
        """)

    conn.commit()

    conn.close()

def get_user_by_email(email):

    conn=get_connection()

    user=conn.execute(
        """
        SELECT *
        FROM users
        WHERE email=?
        """,
        (email,)
    ).fetchone()

    conn.close()

    return user

def create_company(company_name):

    conn=get_connection()

    cur=conn.cursor()


    cur.execute(
        """
        INSERT INTO companies
        (
        name,
        created_at
        )
        VALUES(?,?)
        """,
        (
        company_name,
        datetime.now().isoformat()
        )
    )


    company_id=cur.lastrowid


    conn.commit()

    conn.close()


    return company_id

def create_user(
    company_name,
    email,
    password_hash,
    full_name,
    role
):

    conn=get_connection()

    cur=conn.cursor()


    # Reuse the company if it already exists, otherwise create it.
    # (Without this check, a second person signing up under the same
    # company name would crash on the UNIQUE constraint, or — if the
    # constraint weren't there — silently create a duplicate company
    # that can't see the first person's documents.)

    cur.execute(
        "SELECT id FROM companies WHERE name=?",
        (company_name,)
    )
    existing=cur.fetchone()

    if existing:

        company_id=existing[0]

    else:

        cur.execute(
            """
            INSERT INTO companies
            (name,created_at)
            VALUES (?,?)
            """,
            (
                company_name,
                datetime.now().isoformat()
            )
        )

        company_id=cur.lastrowid



    cur.execute(
        """
        INSERT INTO users
        (
        email,
        password_hash,
        full_name,
        role,
        company_id,
        created_at
        )

        VALUES(?,?,?,?,?,?)
        """,
        (
            email,
            password_hash,
            full_name,
            role,
            company_id,
            datetime.now().isoformat()
        )
    )

    conn.commit()

    conn.close()

def get_company_name(company_id):

    conn=get_connection()

    row=conn.execute(
        "SELECT name FROM companies WHERE id=?",
        (company_id,)
    ).fetchone()

    conn.close()

    return row["name"] if row else ""


def find_duplicate_file(file_hash,company_id):

    conn=get_connection()

    row=conn.execute(
        """
        SELECT *
        FROM documents
        WHERE file_hash=?
        AND company_id=?
        """,
        (
        file_hash,
        company_id
        )
    ).fetchone()

    conn.close()

    return row


def find_duplicate_invoice_number(invoice_number,company_id):
    """
    Primary duplicate check from the brief: match invoice number against
    existing records within this company.
    """

    if not invoice_number:
        return None

    conn=get_connection()

    row=conn.execute(
        """
        SELECT *
        FROM documents
        WHERE invoice_number=?
        AND company_id=?
        AND status!='rejected'
        """,
        (
        invoice_number,
        company_id
        )
    ).fetchone()

    conn.close()

    return row


def find_duplicate_vendor_amount(vendor_name,amount,company_id,tolerance=0.01):
    """
    Secondary duplicate validation from the brief: same vendor + same amount,
    even if the invoice number is different, missing, or wasn't extracted
    correctly. Catches near-duplicate resubmissions.
    """

    if not vendor_name or amount is None:
        return None

    conn=get_connection()

    row=conn.execute(
        """
        SELECT *
        FROM documents
        WHERE vendor_name=?
        AND company_id=?
        AND status!='rejected'
        AND ABS(amount-?)<?
        """,
        (
        vendor_name,
        company_id,
        amount,
        tolerance
        )
    ).fetchone()

    conn.close()

    return row

def create_document(
    file_name,
    file_path,
    file_hash,
    document_type,
    vendor_name,
    invoice_number,
    invoice_date,
    subtotal,
    vat_amount,
    amount,
    uploaded_by,
    company_id,
    is_duplicate=False
    ):

    conn=get_connection()

    cur=conn.cursor()


    status="duplicate" if is_duplicate else "pending"


    cur.execute(
    """
    INSERT INTO documents
    (
    file_name,
    file_path,
    file_hash,
    document_type,
    vendor_name,
    invoice_number,
    invoice_date,
    subtotal,
    vat_amount,
    amount,
    status,
    is_duplicate,
    uploaded_by,
    company_id,
    created_at
    )

    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,

    (
    file_name,
    file_path,
    file_hash,
    document_type,
    vendor_name,
    invoice_number,
    invoice_date,
    subtotal,
    vat_amount,
    amount,
    status,
    int(is_duplicate),
    uploaded_by,
    company_id,
    datetime.now().isoformat()
    )
    )


    document_id=cur.lastrowid



    if not is_duplicate:


        cur.executemany(

        """
        INSERT INTO approvals
        (
        document_id,
        step,
        role_required
        )

        VALUES(?,?,?)

        """,

        [

        (
        document_id,
        1,
        "reviewer"
        ),

        (
        document_id,
        2,
        "manager"
        ),

        (
        document_id,
        3,
        "finance/admin"
        )

        ]

        )

    conn.commit()

    conn.close()

    return document_id

def get_company_documents(company_id):

    conn=get_connection()


    df=pd.read_sql_query(

    """

    SELECT *

    FROM documents

    WHERE company_id=?

    ORDER BY created_at DESC

    """,

    conn,

    params=(company_id,)

    )

    conn.close()

    return df

def get_all_documents(company_id):

    conn=get_connection()


    df=pd.read_sql_query(
    """
    SELECT *

    FROM documents

    WHERE company_id=?

    """,
    conn,
    params=(company_id,)
    )


    conn.close()


    return df

def get_document_approvals(document_id):

    conn=get_connection()


    df=pd.read_sql_query(
    """
    SELECT *

    FROM approvals

    WHERE document_id=?

    ORDER BY step

    """,
    conn,
    params=(document_id,)
    )


    conn.close()


    return df

ROLE_TO_STEP={
"reviewer":1,
"manager":2,
"finance/admin":3
}

def get_company_users(company_id):

    conn=get_connection()


    df=pd.read_sql_query(

    """
    SELECT
    id,
    full_name,
    email,
    role

    FROM users

    WHERE company_id=?

    """,

    conn,

    params=(company_id,)

    )


    conn.close()


    return df

def update_user_role(user_id,role):

    conn=get_connection()
    cur=conn.cursor()
    cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()


def update_user_details(user_id, full_name, email):
    """Update a user's name and email address."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET full_name=?, email=? WHERE id=?",
            (full_name.strip(), email.strip(), int(user_id))
        )
        conn.commit()
        conn.close()
        return True, "User updated successfully."
    except Exception as e:
        conn.close()
        return False, f"Could not update user: {e}"


def delete_user(user_id, current_user_id):
    """Delete a user. Cannot delete yourself."""
    if int(user_id) == int(current_user_id):
        return False, "You cannot delete your own account."
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (int(user_id),))
    conn.commit()
    conn.close()
    return True, "User deleted."

def submit_approval(document_id,step,role,approver_id,action,comments):
    """
    action is 'approved' or 'rejected'.
    Updates this step's approval row, then updates the parent document's
    overall status: any rejection marks the document rejected immediately,
    and approving the final step (3) marks the document approved.
    """

    conn=get_connection()

    cur=conn.cursor()

    cur.execute(
        """
        UPDATE approvals
        SET status=?, approver_id=?, comments=?, actioned_at=?
        WHERE document_id=? AND step=?
        """,
        (
            action,
            approver_id,
            comments,
            datetime.now().isoformat(),
            document_id,
            step
        )
    )

    if action=="rejected":

        cur.execute(
            "UPDATE documents SET status='rejected' WHERE id=?",
            (document_id,)
        )

    elif action=="approved" and step==3:

        cur.execute(
            "UPDATE documents SET status='approved' WHERE id=?",
            (document_id,)
        )

    # steps 1 and 2 approved: document stays 'pending', next step auto-unlocks

    conn.commit()

    conn.close()

def delete_document(document_id):

    conn=get_connection()

    cur=conn.cursor()


    cur.execute(
    "DELETE FROM approvals WHERE document_id=?",
    (document_id,)
    )


    cur.execute(
    "DELETE FROM documents WHERE id=?",
    (document_id,)
    )


    conn.commit()

    conn.close()

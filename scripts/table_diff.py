"""Discovery: which tables does a UI action change? `snap` stores CHECKSUM TABLE for every table; `diff` compares.
Usage: table_diff.py <mysql|postgres> <url> snap <file> | diff <file>"""
import json
import sys

from sqlalchemy import create_engine, text


def tables(conn, dialect):
    if dialect == "mysql":
        return [r[0] for r in conn.execute(text("SHOW TABLES"))]
    return [r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='adempiere' OR schemaname='public'"))]


def state(url, dialect):
    out = {}
    with create_engine(url).connect() as c:
        for t in tables(c, dialect):
            if dialect == "mysql":
                out[t] = str(c.execute(text(f"CHECKSUM TABLE `{t}`")).fetchone()[1])
            else:
                out[t] = str(c.execute(text(f'SELECT count(*), coalesce(sum(hashtext(x::text)),0) FROM "{t}" x')).fetchone())
    return out


def main():
    dialect, url, cmd, path = sys.argv[1:5]
    cur = state(url, dialect)
    if cmd == "snap":
        json.dump(cur, open(path, "w"))
        print("saved", len(cur), "tables")
    else:
        old = json.load(open(path))
        print("changed:", sorted(t for t in cur if old.get(t) != cur[t]))


if __name__ == "__main__":
    main()

class FirstOccurrence:
    def first_occurrence(self, connection, view, segmentation, scope, digest, identity):
        row = connection.execute(
            "INSERT OR IGNORE INTO seen(v,s,g,h,d,a,z,o) VALUES(?,?,?,?,?,?,?,?) RETURNING d,a,z,o",
            (view, segmentation, scope, digest, *identity)
        ).fetchone()
        if row is not None:
            return True, identity
        kept = connection.execute(
            "SELECT d,a,z,o FROM seen WHERE v=? AND s=? AND g=? AND h=?",
            (view, segmentation, scope, digest)
        ).fetchone()
        if kept is None:
            raise ValueError("Dedup lookup failed after ignored insert")
        return False, list(kept)

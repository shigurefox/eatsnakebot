import json
import logging
import sqlite3

class locDBHelper:
    """
    This object handles direct database access.
    """

    def __init__(self,
                 dbname = "loc_db.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self.logger = logging.getLogger("locDBHelper")

        if not self.dbname:
            setup()

    # It's always important to set the table before we have something
    def setup(self):
        try:
            self.logger.debug("Creating table...")
            cmmd = "CREATE TABLE IF NOT EXISTS restaurants (idx INTEGER PRIMARY KEY, \
                                                            name TEXT UNIQUE NOT NULL, \
                                                            pricerange INTEGER, \
                                                            mincharge TEXT, \
                                                            address TEXT, \
                                                            optime TEXT, \
                                                            tags TEXT, \
                                                            latitude REAL, \
                                                            longitude REAL, \
                                                            others TEXT)"
            self.conn.execute(cmmd)
            self.conn.commit()
        except:
            self.logger.exception("Failed to create table or table already exists.")

    # For adding/deleting entries via adm commands
    def add_item(self,
                 rname,
                 prange,
                 mch,
                 addr,
                 opt,
                 lat,
                 lng,
                 tag = None,
                 oths = None):
        try:
            cmmd = "INSERT INTO restaurants (name, pricerange, mincharge, address, optime, latitude, longitude, tag, oths) \
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            args = (rname, prange, mch, addr, opt, lat, lng, tag, oths)
            self.cur.execute(cmmd, args)
            self.conn.commit()
            return True
        except:
            return False

    def remove_item(self, name):
        cmmd = "DELETE FROM restaurants WHERE name = (?)"
        args = (name, )
        self.cur.execute(cmmd, args)
        self.conn.commit()

    # Main function that fetches a choice randomly
    def get_choice(self):
        """
        Returns:
            Dict() of a randomly selected choice.

        """
        try:
            cmmd = "SELECT * FROM restaurants ORDER BY RANDOM() LIMIT 1"
            c = self.cur
            c.execute(cmmd)
            row = c.fetchone()
            return row

        except:
            self.logger.exception("Failed to make a decision D:")

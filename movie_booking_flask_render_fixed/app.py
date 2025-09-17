from flask import Flask, render_template, request, redirect, url_for
import sqlite3, os, threading

app = Flask(__name__)
DB = "app.db"
lock = threading.Lock()

def get_conn():
    return sqlite3.connect(DB)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS theaters (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS halls (
        id INTEGER PRIMARY KEY AUTOINCREMENT, theater_id INTEGER, name TEXT NOT NULL,
        rows INTEGER, seats_per_row INTEGER, FOREIGN KEY(theater_id) REFERENCES theaters(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, price REAL NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS shows (
        id INTEGER PRIMARY KEY AUTOINCREMENT, movie_id INTEGER, hall_id INTEGER, show_time TEXT NOT NULL,
        FOREIGN KEY(movie_id) REFERENCES movies(id), FOREIGN KEY(hall_id) REFERENCES halls(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER, row_index INTEGER, col_index INTEGER, booked INTEGER DEFAULT 0,
        FOREIGN KEY(show_id) REFERENCES shows(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, show_id INTEGER, seats TEXT, customer TEXT,
        FOREIGN KEY(show_id) REFERENCES shows(id))""")
    conn.commit()
    conn.close()

@app.route("/")
def index():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT id, title, price FROM movies")
    movies = c.fetchall()
    conn.close()
    return render_template("index.html", movies=movies)

@app.route("/admin")
def admin():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM theaters"); theaters = c.fetchall()
    c.execute("SELECT * FROM movies"); movies = c.fetchall()
    conn.close()
    return render_template("admin.html", theaters=theaters, movies=movies)

@app.route("/admin/create_sample")
def create_sample():
    conn = get_conn(); c = conn.cursor()
    # sample theaters, halls, movies, shows, seats (layouts)
    c.execute("INSERT INTO theaters (name) VALUES (?)", ("PVR City Center",))
    pvr_id = c.lastrowid
    c.execute("INSERT INTO theaters (name) VALUES (?)", ("INOX Mall",))
    inox_id = c.lastrowid
    # halls: provide rows and seats per row (must be >=6)
    c.execute("INSERT INTO halls (theater_id, name, rows, seats_per_row) VALUES (?, ?, ?, ?)", (pvr_id, "Hall 1", 3, 7))
    hall1 = c.lastrowid
    c.execute("INSERT INTO halls (theater_id, name, rows, seats_per_row) VALUES (?, ?, ?, ?)", (pvr_id, "Hall 2", 3, 10))
    hall2 = c.lastrowid
    c.execute("INSERT INTO halls (theater_id, name, rows, seats_per_row) VALUES (?, ?, ?, ?)", (inox_id, "Hall A", 3, 8))
    hallA = c.lastrowid
    # movies
    c.execute("INSERT INTO movies (title, price) VALUES (?, ?)", ("Inception", 250))
    m1 = c.lastrowid
    c.execute("INSERT INTO movies (title, price) VALUES (?, ?)", ("Interstellar", 300))
    m2 = c.lastrowid
    c.execute("INSERT INTO movies (title, price) VALUES (?, ?)", ("Avengers", 350))
    m3 = c.lastrowid
    # shows for each hall
    shows = [("10:00 AM",),("1:00 PM",),("6:00 PM",),("9:00 PM",)]
    # assign shows
    c.execute("INSERT INTO shows (movie_id, hall_id, show_time) VALUES (?, ?, ?)", (m1, hall1, "10:00 AM"))
    s1 = c.lastrowid
    c.execute("INSERT INTO shows (movie_id, hall_id, show_time) VALUES (?, ?, ?)", (m1, hall1, "6:00 PM"))
    s2 = c.lastrowid
    c.execute("INSERT INTO shows (movie_id, hall_id, show_time) VALUES (?, ?, ?)", (m3, hall2, "7:00 PM"))
    s3 = c.lastrowid
    c.execute("INSERT INTO shows (movie_id, hall_id, show_time) VALUES (?, ?, ?)", (m2, hallA, "6:00 PM"))
    s4 = c.lastrowid
    # generate seats for each show: rows x cols with indices starting at 1
    for show_id, hall_id in ((s1, hall1),(s2, hall1),(s3, hall2),(s4, hallA)):
        c.execute("SELECT rows, seats_per_row FROM halls WHERE id=?", (hall_id,))
        r,s = c.fetchone()
        for ri in range(1, r+1):
            for ci in range(1, s+1):
                c.execute("INSERT INTO seats (show_id, row_index, col_index, booked) VALUES (?, ?, ?, ?)", (show_id, ri, ci, 0))
    # pre-book some seats for demo (example)
    # book A3, A4 in show s3 (hall2)
    c.execute("SELECT id FROM seats WHERE show_id=? AND row_index=? AND col_index IN (?,?)", (s3,1,3,4))
    rows = c.fetchall()
    for row in rows:
        c.execute("UPDATE seats SET booked=1 WHERE id=?", (row[0],))
    conn.commit()
    conn.close()
    return "Sample data created."

@app.route("/shows")
def shows():
    conn = get_conn(); c = conn.cursor()
    c.execute("""SELECT shows.id, movies.title, halls.name, shows.show_time, movies.price
                 FROM shows JOIN movies ON shows.movie_id=movies.id JOIN halls ON shows.hall_id=halls.id""")
    data = c.fetchall()
    conn.close()
    return render_template("shows.html", shows=data)

@app.route("/book/<int:show_id>", methods=["GET","POST"])
def book(show_id):
    conn = get_conn(); c = conn.cursor()
    if request.method == "POST":
        seats = request.form.getlist("seats")
        customer = request.form.get("customer","Guest")
        with lock:
            # verify availability
            for seat_id in seats:
                c.execute("SELECT booked FROM seats WHERE id=?", (seat_id,))
                r = c.fetchone()
                if not r or r[0]==1:
                    conn.close()
                    return "Error: Seat unavailable.", 400
            for seat_id in seats:
                c.execute("UPDATE seats SET booked=1 WHERE id=?", (seat_id,))
            c.execute("INSERT INTO bookings (show_id, seats, customer) VALUES (?, ?, ?)", (show_id, ",".join(seats), customer))
            conn.commit()
        conn.close()
        return redirect(url_for("confirmation", booking_id=c.lastrowid))

    c.execute("SELECT id, row_index, col_index, booked FROM seats WHERE show_id=? ORDER BY row_index, col_index", (show_id,))
    seats = c.fetchall()
    conn.close()
    return render_template("book.html", seats=seats, show_id=show_id)

@app.route("/confirmation/<int:booking_id>")
def confirmation(booking_id):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT bookings.id, shows.show_time, movies.title, bookings.seats, bookings.customer, movies.price FROM bookings JOIN shows ON bookings.show_id=shows.id JOIN movies ON shows.movie_id=movies.id WHERE bookings.id=?", (booking_id,))
    data = c.fetchone()
    conn.close()
    if not data:
        return "Booking not found", 404
    return render_template("confirmation.html", booking=data)

if __name__ == '__main__':
    init_db()
    # create DB file if not exists; Render/Heroku will run via gunicorn
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)

import os
import time
import threading
import tempfile
from datetime import date

from sqlalchemy import (
    Column, Integer, String, Float, Date,
    create_engine, text, event as sa_event,
    select, func,
)
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()




class ImportowanaCena(Base):
    __tablename__ = "demo_ceny"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10))
    data = Column(Date)
    cena = Column(Float)
    zrodlo = Column(String(50))



def engine(path):
    e = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @sa_event.listens_for(e, "connect")
    def _cfg(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")

    return e


def init(e):
    Base.metadata.drop_all(e)
    Base.metadata.create_all(e)


def dump(e):
    with Session(e) as s:
        return [(r.ticker, r.cena, r.zrodlo) for r in s.query(ImportowanaCena).all()]


def print_block(title, data):
    print(f"{title}: {data}")


lock = threading.Lock()



def dirty_read(e):
    print("\nDIRTY READ")
    print_block("PRZED", dump(e))

    res = {"dirty": 0}

    def a(ev1, ev2):
        with Session(e) as s:
            s.add(ImportowanaCena(
                ticker="BTC",
                data=date(2022,1,1),
                cena=50000.0,
                zrodlo="A"
            ))
            s.flush()
            ev1.set()
            ev2.wait()
            s.rollback()

    def b(ev1, ev2):
        ev1.wait()
        with Session(e) as s:
            res["dirty"] = s.query(ImportowanaCena).count()
        ev2.set()

    e1, e2 = threading.Event(), threading.Event()

    t1 = threading.Thread(target=a, args=(e1, e2))
    t2 = threading.Thread(target=b, args=(e1, e2))

    t1.start(); t2.start()
    t1.join(); t2.join()

    print("W TRAKCIE:", res["dirty"])
    print("PO:", dump(e))
    print("Nie ma dirty read w SQLlite")



def lost_update(e):
    print("\nLOST UPDATE")
    print_block("PRZED", dump(e))

    barrier = threading.Barrier(2)

    def worker(name):
        barrier.wait()

        with lock:
            with Session(e) as s:
                if s.query(ImportowanaCena).count() < 5:
                    time.sleep(0.02)

                    s.add_all([
                        ImportowanaCena(
                            ticker="BTC",
                            data=date(2022,1,2),
                            cena=47000.0,
                            zrodlo=name
                        ),
                        ImportowanaCena(
                            ticker="BTC",
                            data=date(2022,1,3),
                            cena=47500.0,
                            zrodlo=name
                        ),
                        ImportowanaCena(
                            ticker="BTC",
                            data=date(2022,1,4),
                            cena=46800.0,
                            zrodlo=name
                        ),
                    ])
                    s.commit()

    t1 = threading.Thread(target=worker, args=("T1",))
    t2 = threading.Thread(target=worker, args=("T2",))

    t1.start(); t2.start()
    t1.join(); t2.join()

    data = dump(e)
    print("PO:", data)
    print("LICZBA:", len(data))



def serializable(e):
    print("\nSERIALIZABLE")
    print_block("PRZED", dump(e))

    barrier = threading.Barrier(2)
    result = {}

    def worker(name):
        barrier.wait()

        for i in range(3):
            try:
                with e.connect() as c:
                    c.execute(text("BEGIN IMMEDIATE"))

                    n = c.execute(
                        select(func.count()).select_from(ImportowanaCena.__table__)
                    ).scalar()

                    if n < 10:
                        c.execute(
                            ImportowanaCena.__table__.insert(),
                            [
                                {
                                    "ticker": "BTC",
                                    "data": date(2022,1,5),
                                    "cena": 47000.0,
                                    "zrodlo": name
                                },
                                {
                                    "ticker": "BTC",
                                    "data": date(2022,1,6),
                                    "cena": 47500.0,
                                    "zrodlo": name
                                },
                                {
                                    "ticker": "BTC",
                                    "data": date(2022,1,7),
                                    "cena": 46800.0,
                                    "zrodlo": name
                                },
                            ],
                        )

                    c.execute(text("COMMIT"))
                    result[name] = "ok"
                    return

            except Exception:
                time.sleep(0.05 * (i + 1))

        result[name] = "fail"

    t1 = threading.Thread(target=worker, args=("T1",))
    t2 = threading.Thread(target=worker, args=("T2",))

    t1.start(); t2.start()
    t1.join(); t2.join()

    print("WORKERS:", result)
    print("PO:", dump(e))




def main():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name

    e = engine(path)
    init(e)

    try:
        dirty_read(e)
        lost_update(e)
        serializable(e)
    finally:
        try:
            os.remove(path)
        except:
            pass



if __name__ == "__main__":
    main()
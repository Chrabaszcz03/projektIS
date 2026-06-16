"""SOAP service for WplywWydarzenNaCenyKryptowalut.

Exposes two endpoints:
  - GetEventCategories()       -> list of category names from the DB
  - GetAnalysisResult(coin, category) -> Welch t-test stats from AnalysisResult table

Run with:
    python soap_service.py

WSDL: http://localhost:7000/?wsdl
"""

from wsgiref.simple_server import make_server

from spyne import Application, Boolean, ComplexModel, Float, Integer, ServiceBase, Unicode
from spyne.decorator import rpc
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from sqlalchemy.orm import Session

from models import AnalysisResult, EventCategory, get_engine


class AnalysisResultType(ComplexModel):
    coin = Unicode
    category = Unicode
    n_event_days = Integer
    n_control_days = Integer
    mean_return_event = Float
    mean_return_control = Float
    t_stat = Float
    p_value = Float
    significant = Boolean
    error = Unicode


class CryptoEventService(ServiceBase):

    @rpc(_returns=Unicode(max_occurs="unbounded"))
    def GetEventCategories(ctx):
        """Return all event category names stored in the database."""
        with Session(get_engine()) as db:
            rows = db.query(EventCategory).order_by(EventCategory.name).all()
            return [r.name for r in rows]

    @rpc(Unicode, Unicode, _returns=AnalysisResultType)
    def GetAnalysisResult(ctx, coin, category):
        """Return Welch t-test statistics for the given coin and category pair."""
        result = AnalysisResultType()
        result.coin = coin
        result.category = category

        with Session(get_engine()) as db:
            row = (
                db.query(AnalysisResult)
                .filter(
                    AnalysisResult.coin == coin.upper(),
                    AnalysisResult.category == category,
                )
                .first()
            )

        if row is None:
            result.error = (
                f"No analysis result found for coin='{coin}' category='{category}'. "
                "Run main.py first to populate the database."
            )
            return result

        result.n_event_days = row.n_event_days
        result.n_control_days = row.n_control_days
        result.mean_return_event = row.mean_return_event
        result.mean_return_control = row.mean_return_control
        result.t_stat = row.t_stat
        result.p_value = row.p_value
        result.significant = bool(row.significant)
        result.error = ""
        return result


application = Application(
    [CryptoEventService],
    tns="pl.krypto.soap",
    in_protocol=Soap11(validator="lxml"),
    out_protocol=Soap11(),
)

wsgi_app = WsgiApplication(application)

if __name__ == "__main__":
    port = 7000
    server = make_server("0.0.0.0", port, wsgi_app)
    print(f"SOAP service running on http://0.0.0.0:{port}/")
    print(f"WSDL: http://localhost:{port}/?wsdl")
    server.serve_forever()

from datetime import datetime, timezone
from uuid import UUID

from app.domain import enums
from app.domain.entities import (
    Address,
    GoodsItem,
    Invoice,
    InvoiceItem,
    Money,
    Party,
    Shipment,
    ShipmentLocation,
    TransportFigure,
    Vehicle,
)
from app.infrastructure.mappers.facturify_payload import FacturifyPayloadBuilder


def test_facturify_payload_contains_carta_porte_block() -> None:
    issuer = Party(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        legal_name="Transportes SA",
        rfc="AAA010101AAA",
        tax_regime="601",
        email="issuer@example.com",
        address=Address(
            street="Calle 1",
            exterior_number="10",
            neighborhood="Centro",
            city="CDMX",
            state="CMX",
            country="MEX",
            zip_code="01020",
        ),
        external_uuid="de305d54-75b4-431b-adb2-eb6b9e546014",
    )
    recipient = Party(
        id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        legal_name="Cliente Demo",
        rfc="CCC010101CCC",
        tax_regime="601",
        email="client@example.com",
        address=issuer.address,
    )
    shipment = Shipment(
        transport_mode=enums.TransportMode.autotransporte_federal,
        permit_type="TPAF",
        permit_number="123",
        total_distance_km=100,
        total_weight_kg=1000,
        vehicle=Vehicle(configuration="VL", plate="ABC1234"),
        locations=[
            ShipmentLocation(
                type=enums.ShipmentLocationType.origin,
                datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
                street="Calle 1",
                exterior_number="10",
                neighborhood="Centro",
                city="CDMX",
                state="CMX",
                country="MEX",
                zip_code="01020",
            ),
            ShipmentLocation(
                type=enums.ShipmentLocationType.destination,
                datetime=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc),
                street="Calle 2",
                exterior_number="20",
                neighborhood="Centro",
                city="GDL",
                state="JAL",
                country="MEX",
                zip_code="44100",
            ),
        ],
        goods=[
            GoodsItem(
                description="Carga",
                product_key="78101800",
                quantity=1,
                unit_key="E48",
                weight_kg=1000,
                value=10000,
            )
        ],
        figures=[
            TransportFigure(type="01", rfc="AAA010101AAA", name="Operador")
        ],
    )
    invoice = Invoice(
        issuer_id=issuer.id,
        recipient=recipient,
        type=enums.InvoiceType.ingreso,
        complement=enums.ComplementType.carta_porte,
        currency="MXN",
        subtotal=Money(10000),
        total=Money(11600),
        cfdi_use="G01",
        payment_form="03",
        payment_method="PUE",
        expedition_place="01020",
        items=[
            InvoiceItem(
                product_key="78101800",
                description="Servicio",
                quantity=1,
                unit_key="E48",
                unit_price=10000,
                taxes={"iva": 16},
            )
        ],
        shipment=shipment,
    )

    builder = FacturifyPayloadBuilder(account_uuid=str(issuer.id))
    payload = builder.build(invoice, issuer)

    assert payload["emisor"]["uuid"] == issuer.external_uuid
    carta_porte = payload["factura"]["Complemento"]["CartaPorte"]
    assert carta_porte["Ubicaciones"]["Ubicacion"][0]["TipoUbicacion"] == "Origen"
    assert carta_porte["Mercancias"]["NumTotalMercancias"] == 1

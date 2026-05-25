from app.services.upload_parser import parse_upload_rows
import pytest


def test_parse_csv_upload_rows() -> None:
    content = (
        "external_id,source,source_url,title,description,address,city,state,zip_code,"
        "price,bedrooms,bathrooms,square_feet,property_type,listing_status,latitude,longitude\n"
        "UPL-1,housing,https://housing.com/upl-1,Test Flat,Desc,\"101 Baner Road, Baner\","
        "Pune,MH,411045,9500000,2,2.0,1150,apartment,for_sale,18.559000,73.786000\n"
    ).encode("utf-8")

    rows = parse_upload_rows("properties.csv", content)

    assert len(rows) == 1
    assert rows[0]["city"] == "Pune"
    assert rows[0]["external_id"] == "UPL-1"


def test_parse_csv_rejects_empty_file() -> None:
    with pytest.raises(ValueError, match="no data"):
        parse_upload_rows("empty.csv", b"external_id,source\n")


def test_parse_xlsx_upload_rows() -> None:
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "external_id",
            "source",
            "source_url",
            "title",
            "description",
            "address",
            "city",
            "state",
            "zip_code",
            "price",
            "bedrooms",
            "bathrooms",
            "square_feet",
            "property_type",
            "listing_status",
            "latitude",
            "longitude",
        ]
    )
    sheet.append(
        [
            "XLS-1",
            "magicbricks",
            "https://magicbricks.com/xls-1",
            "Mumbai Flat",
            "Desc",
            "88 Link Road, Goregaon West",
            "Mumbai",
            "MH",
            "400104",
            13500000,
            3,
            2.5,
            1420,
            "apartment",
            "for_sale",
            19.166,
            72.852,
        ]
    )

    buffer = BytesIO()
    workbook.save(buffer)

    rows = parse_upload_rows("properties.xlsx", buffer.getvalue())

    assert len(rows) == 1
    assert rows[0]["city"] == "Mumbai"
    assert rows[0]["external_id"] == "XLS-1"

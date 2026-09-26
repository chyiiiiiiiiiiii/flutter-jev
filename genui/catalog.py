#!/usr/bin/env python3.13
"""The surface catalogue and the data model both deciders work from.

This mirrors what Flutter's GenUI SDK calls a `Catalog`: the closed set of
widgets the AI is allowed to use, each with a name the AI references and a
schema for its properties. Because the set is closed, choosing from it is a
different kind of problem from writing the payload that describes it — which
is the whole thing being measured here.
"""

from __future__ import annotations

SURFACES: dict[str, str] = {
    "order_list": "A scrollable list of the customer's recent orders, each row "
                  "showing item name, order number, total and status.",
    "order_detail": "One order in full: line items, totals, delivery address, "
                    "payment method, and buttons to track it or return it.",
    "tracking_timeline": "A delivery progress timeline for one order, from "
                         "confirmed through packed, out for delivery and "
                         "delivered, with the carrier and tracking number.",
    "return_form": "A form to start a return for one order: which items, a "
                   "reason dropdown, an optional note, and a confirmation "
                   "checkbox before submitting.",
    "refund_status": "The state of an in-flight refund for one order: request "
                     "received, label issued, item received, money returned.",
    "faq_answer": "A short written answer to a policy question, with a link to "
                  "the full policy page.",
    "contact_form": "A form to open a support ticket: topic, order number, "
                    "message body and an attach-screenshot toggle.",
    "cart_summary": "The current cart: each line with a quantity stepper, plus "
                    "subtotal, shipping and total.",
    "address_picker": "A chooser for which saved delivery address to use.",
    "plain_reply": "No interface is needed; a sentence of text answers this.",
}

# What the app already knows. In the Jev path the code binds these values into
# the payload itself, so the model never has to reproduce them — which is just
# as well, because it cannot emit a string at all.
DATA = {
    "customer": {"name": "Demo account", "email": "demo@example.com"},
    "orders": [
        {"id": "5207", "item": "Pour-over kit", "variant": "Matte white / 600ml",
         "total": "$63.90", "status": "Delivered", "deliveredDaysAgo": 8,
         "carrier": "Harbor Post", "tracking": "HP-7302-118"},
        {"id": "5213", "item": "Pocket speaker", "variant": "Cobalt / Bluetooth",
         "total": "$117.00", "status": "In transit",
         "carrier": "Harbor Post", "tracking": "HP-7302-124"},
        {"id": "5198", "item": "Glass carafe", "variant": "Clear / 1L",
         "total": "$41.90", "status": "Delivered", "deliveredDaysAgo": 19},
        {"id": "5226", "item": "Merino socks", "variant": "Grey / M",
         "total": "$71.90", "status": "Processing"},
    ],
    "policy": {"returnWindowDays": 30, "freeShippingOver": "$100"},
    "cart": [],
}

# The turns a person would actually type, with the surface a designer would
# expect. The expectation is a judgement call, which is why disagreements get
# reported rather than silently scored wrong.
TURNS: list[tuple[str, str]] = [
    ("show me my orders", "order_list"),
    ("what's happening with my speaker", "tracking_timeline"),
    ("I want to send the pour-over kit back", "return_form"),
    ("where is my refund", "refund_status"),
    ("how long do I have to return something", "faq_answer"),
    ("order 5207 details please", "order_detail"),
    ("my parcel hasn't moved in four days, I need help", "contact_form"),
    ("what's in my cart", "cart_summary"),
    ("can you send it to my workshop instead", "address_picker"),
    ("thanks, that's all", "plain_reply"),
    ("track order 5213", "tracking_timeline"),
    ("I got the wrong size", "return_form"),
]

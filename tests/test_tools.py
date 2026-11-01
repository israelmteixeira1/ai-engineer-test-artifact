from datetime import date

import pytest

from emporio.data import load_policies, load_store
from emporio.store import ConversationStore
from emporio.tools import TOOL_DEFINITIONS, Tools, evaluate_return, max_installments


@pytest.fixture(scope="module")
def store():
    return load_store()


@pytest.fixture
def tools(store, monkeypatch):
    monkeypatch.setenv("EMPORIO_NOW", "2026-03-25T10:00:00")
    return Tools(store, load_policies(), ConversationStore(), "t")


def names(result):
    return [p["nome"] for p in result["produtos"]]


def test_exact_model_search_ignores_case_accents_and_hyphen(tools):
    assert names(tools.buscar_produtos(termo="takamine gd-20"))[0] == "Takamine GD20 Dreadnought Natural"


def test_typo_is_tolerated(tools):
    assert names(tools.buscar_produtos(termo="takamini GD20"))[0] == "Takamine GD20 Dreadnought Natural"


def test_acoustic_guitars_under_1000_exclude_unavailable(tools):
    result = tools.buscar_produtos(categoria="Violões", preco_max=1000, limite=50)
    found = names(result)
    assert "Yamaha C40 Nylon Natural" in found
    assert "Giannini GF-3D Dreadnought Sunburst" not in found
    assert "Shelby SN-7C 7 Cordas Nylon Natural" not in found
    assert {p["nome"] for p in result["indisponiveis_encontrados"]} >= {"Giannini GF-3D Dreadnought Sunburst"}


def test_price_filter_uses_promotional_price(tools):
    # Ohana CK-20 lists at 549 with 20% off (439.20).
    assert "Ohana CK-20 Concert Natural" in names(tools.buscar_produtos(categoria="Ukuleles", preco_max=450, limite=50))


def test_only_active_promotion_applies(tools):
    assert 96 not in tools.store.promotions  # past 18% and 40% campaigns
    crafter = tools.buscar_produtos(termo="Crafter HT-100")["produtos"][0]
    assert crafter["promocao"]["preco_promocional"] == 1967.18


@pytest.mark.parametrize("term,label", [("Ibanez Bass 2X", "descontinuado"), ("KA-ABP-CTG", "em breve")])
def test_unsellable_with_positive_stock_is_never_available(tools, term, label):
    result = tools.buscar_produtos(termo=term)
    assert result["produtos"] == []
    assert result["indisponiveis_encontrados"][0]["disponibilidade"].startswith(label)
    assert "preco_tabela" not in result["indisponiveis_encontrados"][0]


def test_unreliable_description_is_withheld(tools):
    product = tools.buscar_produtos(termo="Yamaha Bass 3X")["produtos"][0]
    assert "descricao" not in product and "aviso" in product


def test_empty_category_reports_nothing(tools):
    assert tools.buscar_produtos(categoria="Cordas Orquestrais")["total_encontrados"] == 0


def test_payment_pix_discount_only_without_promotion(tools):
    plain = tools.simular_pagamento([{"product_id": 95, "quantidade": 1}])
    assert plain["total"] == 2199 and plain["total_pix"] == 2089.05
    promo = tools.simular_pagamento([{"product_id": 90, "quantidade": 1}])
    assert promo["total"] == promo["total_pix"] == 1967.18


def test_payment_mixed_cart_and_stock_check(tools):
    mixed = tools.simular_pagamento([{"product_id": 95, "quantidade": 1}, {"product_id": 90, "quantidade": 1}])
    assert mixed["total_pix"] == round(2089.05 + 1967.18, 2)
    assert "erro" in tools.simular_pagamento([{"product_id": 90, "quantidade": 99}])
    assert "erro" in tools.simular_pagamento([{"product_id": 96, "quantidade": 1}])
    assert "erro" in tools.simular_pagamento([{"product_id": 130, "quantidade": 1}])


@pytest.mark.parametrize("total,expected", [
    (40, 0), (50, 1), (159.9, 3), (319, 3), (320, 4), (480, 6), (699.9, 6), (700, 7), (1199, 11), (1200, 12), (11499, 12),
])
def test_installment_tiers(total, expected):
    assert max_installments(total) == expected


def test_order_requires_matching_contact(tools):
    assert "erro" in tools.consultar_pedido(numero_pedido=8)
    assert "erro" in tools.consultar_pedido(numero_pedido=8, telefone="(67) 90000-0000")
    found = tools.consultar_pedido(numero_pedido=8, telefone="+55 67 99654-7821")
    assert found["pedidos"][0]["codigo_rastreio"] == "BRJL5544332BR"
    assert "alerta" in found["pedidos"][0]


def test_wrong_and_missing_order_are_indistinguishable(tools):
    assert tools.consultar_pedido(numero_pedido=8, telefone="1") == tools.consultar_pedido(numero_pedido=999, telefone="1")


def test_shared_email_does_not_mix_customers(tools):
    # bruno.martins@jmail.com belongs to customers 11 and 43; only customer 11 has orders.
    assert tools.consultar_pedido(telefone="(67) 98543-2109", email="bruno.martins@jmail.com")["pedidos"][0]["numero_pedido"] == 10
    assert tools.consultar_pedido(telefone="(67) 99456-3456", email="bruno.martins@jmail.com")["pedidos"] == []


def test_lockout_after_repeated_failures(tools):
    for _ in range(5):
        tools.consultar_pedido(numero_pedido=8, telefone="1")
    assert "Limite" in tools.consultar_pedido(numero_pedido=8, telefone="(67) 99654-7821")["erro"]
    assert "Limite" in tools.avaliar_devolucao(8, "defeito", telefone="(67) 99654-7821")["erro"]


DELIVERED = {"status": "delivered", "order_date": "2026-01-18", "estimated_delivery": "2026-02-01"}


@pytest.mark.parametrize("received,today,expected", [
    ("2026-02-01", date(2026, 2, 8), "elegivel"),
    ("2026-02-01", date(2026, 2, 9), "fora_do_prazo"),
])
def test_regret_window_boundary(received, today, expected):
    assert evaluate_return(DELIVERED, "arrependimento", today, received, True)["resultado"] == expected


def test_regret_needs_online_and_receipt_date():
    today = date(2026, 2, 3)
    assert evaluate_return(DELIVERED, "arrependimento", today)["resultado"] == "precisa_informar"
    assert evaluate_return(DELIVERED, "arrependimento", today, None, False)["resultado"] == "nao_aplicavel"
    assert evaluate_return(DELIVERED, "arrependimento", today, None, True)["precisa_informar"].startswith("data_recebimento")


def test_defect_uses_purchase_date_then_warranty():
    assert evaluate_return(DELIVERED, "defeito", date(2026, 2, 17))["resultado"] == "elegivel_troca_na_loja"
    late = evaluate_return(DELIVERED, "defeito", date(2026, 3, 25), "2026-01-30")
    assert late["resultado"] == "fora_do_prazo_de_troca" and late["garantia_legal_90_dias_vigente"] is True


def test_return_blocked_for_undelivered_cancelled_and_bad_dates():
    assert evaluate_return({**DELIVERED, "status": "confirmed"}, "defeito", date(2026, 2, 3))["resultado"] == "nao_recebido"
    assert evaluate_return({**DELIVERED, "status": "cancelled"}, "defeito", date(2026, 2, 3))["resultado"] == "nao_aplicavel"
    assert "erro" in evaluate_return(DELIVERED, "preferencia", date(2026, 2, 3), "2030-01-01")


def test_handoff_creates_ticket_with_policy_sla(tools):
    result = tools.encaminhar_atendente("reclamacao", "Atraso no pedido 8", "(67) 99654-7821")
    assert result["protocolo"] == "EMP-00001" and "24 horas" in result["prazo_retorno"]


def test_policy_sections_match_tool_enum_and_resolved_contacts(tools):
    schema = next(t for t in TOOL_DEFINITIONS if t["name"] == "consultar_politicas")["input_schema"]
    assert set(schema["properties"]["secoes"]["items"]["enum"]) == set(tools.policies)
    assert "3341-4444" in tools.policies["sobre"] and "3321-4500" not in " ".join(tools.policies.values())


@pytest.mark.parametrize("term,count", [("baixo", 3), ("piano", 3), ("flauta", 0), ("palheta", 0), ("cabo", 0)])
def test_singular_terms_match_category_without_false_positives(tools, term, count):
    assert tools.buscar_produtos(termo=term)["total_encontrados"] == count


def test_electric_filter_does_not_hide_electric_guitars(tools):
    assert tools.buscar_produtos(categoria="Guitarras", eletrico=True)["total_encontrados"] == 5
    assert tools.buscar_produtos(categoria="Violões", eletrico=True, tipo_corda="nylon")["total_encontrados"] > 0


def test_order_number_as_string_is_accepted(tools):
    assert tools.consultar_pedido(numero_pedido="6", telefone="(67) 98654-3210")["pedidos"][0]["cliente"] == "Gabriel"

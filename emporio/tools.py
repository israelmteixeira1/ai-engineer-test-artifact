from datetime import date, timedelta
from difflib import get_close_matches

from . import clock
from .data import Store, digits, normalize
from .store import ConversationStore

MAX_FAILED_VERIFICATIONS = 5
PIX_DISCOUNT = 0.05
STOPWORDS = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "um", "uma", "para", "pra", "com", "e", "em"}
AVAILABILITY = {
    "discontinued": "descontinuado: não faz mais parte do catálogo",
    "coming_soon": "em breve: ainda não está à venda",
}
ORDER_STATUS = {
    "pending": "pendente: aguardando confirmação de pagamento ou processamento",
    "confirmed": "confirmado: em preparação, ainda não despachado",
    "shipped": "enviado: em transporte",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
NOT_VERIFIED = (
    "Não foi possível localizar pedido com esses dados. Não revele se o pedido ou o contato existem. "
    "Peça ao cliente para conferir os dados."
)

TOOL_DEFINITIONS = [
    {
        "name": "buscar_produtos",
        "description": (
            "Consulta o catálogo em tempo real: preço, promoção vigente, estoque e status. Use sempre que o "
            "cliente falar de produto, preço, disponibilidade ou promoção de um item. Também serve para achar "
            "alternativas a um produto indisponível."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "Modelo, marca ou característica, ex.: 'Takamine GD20'."},
                "categoria": {
                    "type": "string",
                    "enum": [
                        "Guitarras", "Baixos", "Baterias e Percussão", "Teclados e Pianos", "Violões",
                        "Instrumentos de Sopro (Madeiras)", "Instrumentos de Sopro (Metais)",
                        "Cordas Orquestrais", "Ukuleles",
                    ],
                },
                "preco_min": {"type": "number", "description": "Sobre o preço final, com promoção."},
                "preco_max": {"type": "number", "description": "Sobre o preço final, com promoção."},
                "tipo_corda": {"type": "string", "enum": ["nylon", "steel"], "description": "steel = aço."},
                "eletrico": {"type": "boolean", "description": "Filtra violões e ukuleles por captação. Guitarras, baixos e teclados não são afetados."},
                "apenas_disponiveis": {
                    "type": "boolean",
                    "description": "Padrão true. Itens indisponíveis que casarem vão em 'indisponiveis_encontrados'.",
                },
            },
        },
    },
    {
        "name": "simular_pagamento",
        "description": (
            "Calcula o total de uma compra, o valor no PIX e o parcelamento máximo conforme as regras da loja. "
            "Use sempre que o cliente perguntar sobre parcelas, PIX ou total. Não inclui frete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "quantidade": {"type": "integer", "minimum": 1},
                        },
                        "required": ["product_id", "quantidade"],
                    },
                }
            },
            "required": ["itens"],
        },
    },
    {
        "name": "consultar_politicas",
        "description": (
            "Lê o manual da loja. Seções: sobre (endereço, contatos, CNPJ, o que a loja vende); horario; "
            "pagamento (formas e regras); trocas_devolucoes; frete (valores, prazos, rastreamento); "
            "promocoes (regras e calendário); garantia; privacidade (LGPD). Consulte antes de responder "
            "sobre qualquer um desses temas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "secoes": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "sobre", "horario", "pagamento", "trocas_devolucoes", "frete",
                            "promocoes", "garantia", "privacidade",
                        ],
                    },
                }
            },
            "required": ["secoes"],
        },
    },
    {
        "name": "consultar_pedido",
        "description": (
            "Consulta status, itens, rastreio e previsão de pedidos do próprio cliente. Exige verificação: "
            "numero_pedido + (telefone ou email), ou telefone + email para listar todos os pedidos. "
            "Peça esses dados ao cliente. Nunca os deduza nem os invente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_pedido": {"type": "integer"},
                "telefone": {"type": "string"},
                "email": {"type": "string"},
            },
        },
    },
    {
        "name": "avaliar_devolucao",
        "description": (
            "Aplica as regras e os prazos de devolução, troca e garantia a um pedido real e calcula os dias "
            "corridos. Use quando o cliente quiser devolver ou trocar um pedido. Exige numero_pedido + "
            "(telefone ou email). A data de recebimento vem do cliente: o sistema só tem a previsão."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "numero_pedido": {"type": "integer"},
                "telefone": {"type": "string"},
                "email": {"type": "string"},
                "motivo": {"type": "string", "enum": ["arrependimento", "defeito", "preferencia"]},
                "data_recebimento": {"type": "string", "description": "AAAA-MM-DD, informada pelo cliente."},
                "compra_online": {"type": "boolean", "description": "Informada pelo cliente; só omita se ele não disse."},
            },
            "required": ["numero_pedido", "motivo"],
        },
    },
    {
        "name": "encaminhar_atendente",
        "description": (
            "Registra um chamado para a equipe humana. Use em reclamações, pedidos que exigem ação no sistema "
            "(efetivar devolução, cancelar, corrigir dados), atrasos, ou quando as ferramentas não resolverem. "
            "Confirme o contato do cliente antes de chamar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string", "enum": ["reclamacao", "devolucao", "pedido", "duvida", "outro"]},
                "resumo": {"type": "string", "description": "Fatos relevantes, para o atendente não precisar perguntar de novo."},
                "contato": {"type": "string", "description": "Telefone ou e-mail informado pelo cliente."},
            },
            "required": ["motivo", "resumo", "contato"],
        },
    },
]


class Tools:
    def __init__(self, store: Store, policies: dict[str, str], conversations: ConversationStore, session_id: str):
        self.store = store
        self.policies = policies
        self.conversations = conversations
        self.session_id = session_id
        self.failed_verifications = 0

    def run(self, name: str, args: dict) -> dict:
        handler = {d["name"]: getattr(self, d["name"]) for d in TOOL_DEFINITIONS}.get(name)
        if handler is None:
            raise ValueError(f"Ferramenta desconhecida: {name}")
        return handler(**args)

    def _availability(self, product: dict) -> tuple[bool, str]:
        if product["status"] in AVAILABILITY:
            return False, AVAILABILITY[product["status"]]
        if product["stock"] <= 0:
            return False, "temporariamente indisponível: sem estoque"
        return True, "disponível"

    def _final_price(self, product: dict) -> float:
        promo = self.store.promotions.get(product["id"])
        return round(product["price"] * (1 - promo["percent"] / 100), 2) if promo else product["price"]

    def _present(self, product: dict) -> dict:
        available, label = self._availability(product)
        promo = self.store.promotions.get(product["id"])
        result = {
            "product_id": product["id"],
            "nome": product["name"],
            "categoria": product["category"],
            "disponibilidade": label,
            "estoque": product["stock"] if available else 0,
            "especificacoes": product["specs"],
        }
        if product["status"] == "active":
            result["preco_tabela"] = product["price"]
            if promo:
                result["promocao"] = {
                    "nome": promo["name"],
                    "desconto_percentual": promo["percent"],
                    "preco_promocional": self._final_price(product),
                }
        if product["description"]:
            result["descricao"] = product["description"]
        else:
            result["aviso"] = "Descrição em revisão: não afirme detalhes além de nome, preço e disponibilidade."
        return result

    def _match_rank(self, product: dict, tokens: list[str]) -> int:
        name_words = product["search_name"].split()
        fuzzy_words = name_words + product["search_category"].split()
        all_words = product["search_all"].split()
        compact_name = product["search_name"].replace(" ", "")
        if "".join(tokens) in compact_name:
            return 3 * len(tokens)
        score = 0
        for token in tokens:
            if token in name_words or (len(token) >= 3 and token in compact_name):
                score += 3
            elif token in all_words:
                score += 1
            elif len(token) >= 4 and get_close_matches(token, fuzzy_words, n=1, cutoff=0.8):
                score += 2
            else:
                return 0
        return score

    def buscar_produtos(
        self, termo=None, categoria=None, preco_min=None, preco_max=None,
        tipo_corda=None, eletrico=None, apenas_disponiveis=True, limite=15,
    ) -> dict:
        tokens = [t for t in normalize(termo or "").split() if t not in STOPWORDS]
        scored = []
        for product in self.store.products.values():
            rank = self._match_rank(product, tokens) if tokens else 1
            final = self._final_price(product)
            specs = product["specs"]
            if (
                rank
                and (categoria is None or product["category"] == categoria)
                and (preco_min is None or final >= preco_min)
                and (preco_max is None or final <= preco_max)
                and (tipo_corda is None or specs.get("strings") == tipo_corda)
                and (eletrico is None or "electronics" not in specs or specs["electronics"] == ("yes" if eletrico else "no"))
            ):
                scored.append((-rank, final, product))
        scored.sort(key=lambda entry: entry[:2])
        products = [entry[2] for entry in scored]
        available = [p for p in products if self._availability(p)[0]]
        unavailable = [p for p in products if not self._availability(p)[0]]
        shown = available if apenas_disponiveis else products
        result = {"total_encontrados": len(shown), "produtos": [self._present(p) for p in shown[:limite]]}
        if len(shown) > limite:
            result["observacao"] = f"Mostrando os {limite} primeiros. Refine a busca se necessário."
        if apenas_disponiveis and unavailable:
            result["indisponiveis_encontrados"] = [self._present(p) for p in unavailable[:3]]
        if not products:
            result["observacao"] = "Nada no sistema com esses critérios. Não afirme que a loja tem esse item."
        return result

    def simular_pagamento(self, itens: list[dict]) -> dict:
        lines, total, pix_total = [], 0.0, 0.0
        for item in itens:
            product = self.store.products.get(item["product_id"])
            quantity = item["quantidade"]
            if product is None:
                return {"erro": f"Produto {item['product_id']} não existe."}
            available, label = self._availability(product)
            if not available:
                return {"erro": f"{product['name']} não pode ser vendido agora ({label})."}
            if quantity < 1 or quantity > product["stock"]:
                return {"erro": f"{product['name']}: quantidade inválida; estoque atual {product['stock']}."}
            promo = self.store.promotions.get(product["id"])
            subtotal = round(self._final_price(product) * quantity, 2)
            pix = subtotal if promo else round(subtotal * (1 - PIX_DISCOUNT), 2)
            total += subtotal
            pix_total += pix
            lines.append({
                "nome": product["name"], "quantidade": quantity, "subtotal": subtotal,
                "promocao": f"{promo['name']} ({promo['percent']:g}%)" if promo else None,
                "subtotal_pix": pix,
            })
        total, pix_total = round(total, 2), round(pix_total, 2)
        installments = max_installments(total)
        return {
            "itens": lines,
            "total": total,
            "total_pix": pix_total,
            "observacao_pix": "Desconto de 5% somente em itens sem promoção; descontos não são cumulativos.",
            "parcelamento_maximo_sem_juros": (
                {"parcelas": installments, "valor_parcela": round(total / installments, 2)} if installments else None
            ),
            "permite_combinar_formas": total > 2000,
            "frete": "não incluído",
        }

    def consultar_politicas(self, secoes: list[str]) -> dict:
        return {s: self.policies.get(s, "Seção inexistente.") for s in secoes}

    def _order_rejected(self) -> dict:
        self.failed_verifications += 1
        if self.failed_verifications >= MAX_FAILED_VERIFICATIONS:
            return self._locked()
        return {"erro": NOT_VERIFIED}

    def _locked(self) -> dict:
        return {"erro": "Limite de tentativas atingido nesta conversa. Oriente o cliente a falar com a equipe da loja."}

    def _verify_order(self, order_id, phone, email) -> dict | None:
        order = self.store.orders.get(int(order_id))
        if not order:
            return None
        customer = self.store.customers[order["customer_id"]]
        phone_ok = bool(phone) and digits(phone) == customer["phone"]
        email_ok = bool(email) and email.strip().lower() == customer["email"]
        return order if phone_ok or email_ok else None

    def _present_order(self, order: dict) -> dict:
        today = clock.now().date()
        estimate = order["estimated_delivery"] or None
        result = {
            "numero_pedido": int(order["order_id"]),
            "data": order["order_date"],
            "status": ORDER_STATUS[order["status"]],
            "itens": [
                {"nome": self.store.products[i["product_id"]]["name"], "quantidade": i["quantity"]}
                for i in self.store.items.get(int(order["order_id"]), [])
            ],
            "total_pago": float(order["total_brl"]),
            "pagamento": order["payment_method"],
            "codigo_rastreio": order["tracking_code"] or None,
            "previsao_entrega": estimate,
            "cliente": self.store.customers[order["customer_id"]]["name"].split()[0],
        }
        if order["notes"]:
            result["observacao"] = order["notes"]
        if order["status"] == "shipped" and estimate and date.fromisoformat(estimate) < today:
            result["alerta"] = (
                f"Previsão vencida há {(today - date.fromisoformat(estimate)).days} dias. "
                "Peça desculpas e ofereça encaminhar à equipe."
            )
        return result

    def consultar_pedido(self, numero_pedido=None, telefone=None, email=None) -> dict:
        if self.failed_verifications >= MAX_FAILED_VERIFICATIONS:
            return self._locked()
        if numero_pedido is not None and (telefone or email):
            order = self._verify_order(numero_pedido, telefone, email)
            return {"pedidos": [self._present_order(order)]} if order else self._order_rejected()
        if telefone and email:
            # customers 11 and 43 share an e-mail
            for customer_id, customer in self.store.customers.items():
                if customer["phone"] == digits(telefone) and customer["email"] == email.strip().lower():
                    orders = [o for o in self.store.orders.values() if o["customer_id"] == customer_id]
                    return {"pedidos": [self._present_order(o) for o in orders]}
            return self._order_rejected()
        return {"erro": "Dados insuficientes. Peça número do pedido + telefone ou e-mail, ou telefone + e-mail."}

    def avaliar_devolucao(
        self, numero_pedido, motivo, telefone=None, email=None, data_recebimento=None, compra_online=None,
    ) -> dict:
        if self.failed_verifications >= MAX_FAILED_VERIFICATIONS:
            return self._locked()
        if not (telefone or email):
            return {"erro": "Dados insuficientes. Peça telefone ou e-mail do pedido."}
        order = self._verify_order(numero_pedido, telefone, email)
        if not order:
            return self._order_rejected()
        return evaluate_return(order, motivo, clock.now().date(), data_recebimento, compra_online)

    def encaminhar_atendente(self, motivo: str, resumo: str, contato: str) -> dict:
        ticket = self.conversations.add_ticket(self.session_id, motivo, resumo, contato, clock.now().isoformat())
        deadline = "até 24 horas úteis" if motivo == "reclamacao" else "não definido em política; não prometa prazo específico"
        return {"protocolo": f"EMP-{ticket:05d}", "registrado": True, "prazo_retorno": deadline}


def max_installments(total: float) -> int:
    # manual, section 3.1
    for n in range(12, 0, -1):
        minimum = 100 if n >= 7 else 80 if n >= 4 else 50
        if total / n >= minimum:
            return n
    return 0


def evaluate_return(order: dict, reason: str, today: date, received=None, online=None) -> dict:
    conditions = (
        "Não elegíveis: personalização ou ajuste sob encomenda, liquidação com aviso de venda final, "
        "boquilhas de sopro. Confirme com o cliente, pois o sistema não registra isso."
    )
    next_step = "A efetivação é feita pela equipe: use encaminhar_atendente se o cliente quiser seguir."
    if order["status"] == "cancelled":
        return {"resultado": "nao_aplicavel", "explicacao": "O pedido já está cancelado."}
    if order["status"] in ("pending", "confirmed", "shipped"):
        return {
            "resultado": "nao_recebido",
            "explicacao": f"O pedido ainda não foi entregue (status {order['status']}). O manual não define "
                          "regra de cancelamento antes da entrega; não prometa cancelamento e encaminhe à equipe.",
        }
    order_date = date.fromisoformat(order["order_date"])
    received_date = None
    if received:
        try:
            received_date = date.fromisoformat(received)
        except ValueError:
            return {"erro": "data_recebimento deve estar no formato AAAA-MM-DD."}
        if received_date > today or received_date < order_date:
            return {"erro": f"Data de recebimento inconsistente: pedido feito em {order_date}, hoje é {today}. Confirme com o cliente."}

    if reason == "defeito":
        days = (today - order_date).days
        result = {"dias_desde_a_compra": days}
        if days <= 30:
            return result | {"resultado": "elegivel_troca_na_loja", "prazo": "até 30 dias corridos da compra",
                             "condicao": "Não cobre mau uso, quedas, umidade ou modificações. " + conditions,
                             "proximo_passo": next_step}
        result |= {"resultado": "fora_do_prazo_de_troca",
                   "alternativa": "Garantia com o fabricante; a loja pode intermediar a pedido do cliente."}
        if not received_date:
            return result | {"precisa_informar": "data_recebimento, para checar a garantia legal de 90 dias",
                             "previsao_entrega": order["estimated_delivery"]}
        warranty_days = (today - received_date).days
        return result | {"dias_desde_o_recebimento": warranty_days, "garantia_legal_90_dias_vigente": warranty_days <= 90,
                         "proximo_passo": next_step}

    if reason == "arrependimento" and online is None:
        return {"resultado": "precisa_informar", "precisa_informar": "compra_online: o direito de arrependimento vale para compras online"}
    if reason == "arrependimento" and online is False:
        return {"resultado": "nao_aplicavel",
                "explicacao": "O arrependimento em 7 dias vale para compras online. Avalie troca por preferência ou encaminhe à equipe."}
    if not received_date:
        return {"resultado": "precisa_informar", "precisa_informar": "data_recebimento: o sistema só tem a previsão",
                "previsao_entrega": order["estimated_delivery"]}
    days = (today - received_date).days
    deadline = received_date + timedelta(days=7)
    if days > 7:
        return {"resultado": "fora_do_prazo", "dias_desde_o_recebimento": days, "prazo_encerrado_em": deadline.isoformat(),
                "alternativa": "Se houver defeito de fabricação, avalie com motivo=defeito."}
    terms = {
        "arrependimento": "Embalagem original, sem uso, com acessórios e manuais. Reembolso na forma original "
                          "em até 10 dias úteis. Frete de devolução por conta da loja.",
        "preferencia": "Perfeito estado, embalagem original, conforme estoque do produto desejado. "
                       "Diferenças de valor são cobradas ou reembolsadas.",
    }
    return {"resultado": "elegivel", "dias_desde_o_recebimento": days, "prazo_ate": deadline.isoformat(),
            "condicoes": f"{terms[reason]} {conditions}", "proximo_passo": next_step}

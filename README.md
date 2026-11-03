# Empório da Música: customer-service agent

A Python text agent ("Tom") that answers Empório da Música customers about products, prices, orders and store policies. It speaks Brazilian Portuguese, because the customers do; this documentation is in English, as the process requires.

## Run it

Requires Python 3.11+ and an [Anthropic API key](https://console.anthropic.com).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then set ANTHROPIC_API_KEY

python -m emporio                 # start a conversation
python -m emporio --debug         # also show every tool call and result
python -m emporio --session ana   # reuse an id to resume that conversation

pytest                            # 49 tests; no API key or network needed
python scripts/generate_examples.py   # regenerate examples/ with the real model
```

`EMPORIO_MODEL` overrides the model. `EMPORIO_NOW=2026-03-25T10:00:00` freezes the clock.

## Architecture

```
customer -> CLI -> Agent loop <-> Claude (Messages API)
                       |
                       v
    buscar_produtos      catalog, stock, active promotions (CSV)
    simular_pagamento    totals, PIX, installment rules (code)
    consultar_politicas  sections of knowledge/policies.md
    consultar_pedido     orders, after identity verification (CSV)
    avaliar_devolucao    return and warranty rules with date math (code)
    encaminhar_atendente human handoff ticket (SQLite)
```

## Technical decisions

**Function calling, with no agent framework.** The questions fall into a small, known set of intents, so purpose-built tools fit well. The whole agent module is under 100 lines (`emporio/agent.py`), so nothing is hidden from debugging. A framework would add dependencies without solving any problem this project has.

**The model decides what to ask; code decides what is true.** The manual warns that wrong prices can amount to misleading advertising, so prices, discounts, installments and deadlines are computed in Python and unit-tested. The LLM chooses tools and writes the reply. It does not do the arithmetic.

**No SQL agent.** Generated SQL over a table with customer phones and e-mails would make privacy depend on the model's behaviour. Fixed tools make it impossible to query another customer's data without passing verification.

**Section lookup instead of a vector database for policies.** The manual is 8 pages with clearly separated topics. Embeddings would add a chance of missing the right chunk with no gain, so the model picks from 8 named sections and always gets the whole section. Vector retrieval becomes worthwhile if the knowledge base grows to many documents.

**Model: Claude Opus 5.5, medium effort.** I chose the most capable current Opus because this agent's failures (a wrong tool, a broken rule) are worse than a small increase in cost, and policy questions require some reasoning. The model is one environment variable away from a cheaper option. I have not measured whether a cheaper model holds the same quality; that comparison should come before production. Refusal fallbacks are enabled through the server-side `fallbacks` parameter.

**Prompt strategy.** The system prompt, in Portuguese, defines the persona, which tool answers which kind of question, the manual's service rules, scope and injection resistance. Customer text and tool results are treated as data. The current date and time go in a mid-conversation system message, so the prompt stays stable and cacheable.

**CLI interface.** The challenge's focus is the agent working correctly, and a CLI shows that with the least extra code. `Agent.reply(text)` is independent of the interface, so a WhatsApp webhook could call it directly.

**Conversation persistence in SQLite.** Customers on a messaging channel come back later and should not have to repeat themselves. A turn is stored only after it completes, so a failed API call cannot corrupt a conversation. History is append-only.

**Privacy (LGPD).** Order tools require the order number plus phone or e-mail, or phone plus e-mail. Wrong data and non-existent orders return the same answer, so the agent cannot be used to test whether an order exists. Five failed attempts lock order lookups for that conversation.

## Data treatment

The CSVs were profiled and compared with the manual before designing the tools. Findings:

| Finding | Treatment |
|---|---|
| The manual gives two WhatsApp numbers: (67) 3341-4444 (cover, company data) and (67) 3321-4500 (section 7) | Use 3341-4444, the one in the company data table. **Assumption, needs store confirmation** |
| E-mail appears both as `emporiodamusica` and with an accented `empóriodamusica` domain | Use the unaccented form from the cover |
| The payment table says a R$ 100 minimum installment, while section 3.1 has tiers; the "up to 3x" text is ambiguous | Section 3.1 is more specific: R$ 50 up to 3x, R$ 80 for 4x-6x, R$ 100 for 7x-12x |
| Section 4.2 sends defects to the manufacturer after 30 days, while section 8.1 grants a 90-day legal warranty from receipt | Report both: store exchange up to 30 days, and whether the legal warranty is still in force |
| Products 135, 136, 137, 139, 140, 142 and 144 have descriptions contradicting their name or specs (e.g. "Yamaha Bass 3X" described as a 5-string Ibanez) | Withhold the description; keep name, price and status. The agent offers to confirm details with the team |
| Product 136 is discontinued with 13 in stock; product 130 is `coming_soon` with 2 in stock | `status` wins: neither is offered for sale and no price is quoted |
| Product 96 is `active` with zero stock and two expired promotions, one of 40% | Reported as temporarily unavailable, with alternatives; the old discounts are never applied |
| Only `is_active = 1` promotions are valid (4 of 25), regardless of the calendar | The promotions table is the only source |
| Customers 11 and 43 share an e-mail address | A shared e-mail alone never verifies an order; the phone is required |
| Totals of orders 3 and 20 differ from current prices (3450 vs 3498; 1400 vs 1488) | The agent reports the amount stored on the order and does not try to explain the difference |
| Order 8 is `shipped` with an estimated delivery in the past | The tool raises an alert; the agent apologizes and offers a handoff |
| Orders have no delivery date | The return tool asks the customer for the receipt date instead of treating the estimate as fact |
| The manual claims 300+ instruments and sells wind and orchestral instruments; the data has 65 products and none in those three categories | The agent reports only what is in the system |

## Assumptions

- Current date: the real clock by default. The dataset ends in March 2026, so with today's date every delivered order is outside the return windows. The examples freeze the clock at 2026-03-25 so that they stay meaningful.
- The 7-day "preference" exchange counts from receipt, as the regret right does; the manual does not say.
- Status descriptions (for example, `confirmed` meaning "being prepared") are my reading of the data, which has no definitions.
- The manual has no rule for cancelling an undelivered order, so the agent promises nothing and hands off.
- Persona name "Tom" is my choice, a play on the musical term; the manual only defines the tone of voice.

## Known limitations and next steps

- Holidays are not modeled: store hours follow the weekly schedule only. I would add a holiday calendar.
- The CSVs are loaded once at startup. "Real time" would mean replacing the loader with database queries; the tool interfaces can stay the same.
- Shipping cannot be quoted, since the data has no CEP, weight or dimensions, and "metropolitan region" is not defined in terms of cities.
- Tickets are only recorded in SQLite. Production needs a real integration with the team's queue.
- Phone or e-mail is weak identification, and the failed-attempt counter resets with each new process. Production should use the WhatsApp sender's number and limits at the channel level.
- The unit tests cover tools and the loop deterministically, using a fake client. There is no automated evaluation of reply quality. With more time, I would build a graded set of real conversations and use it to compare models and prompt changes.
- No streaming, token-usage monitoring or tracing.

## Conversation examples

`examples/` holds five transcripts produced by `scripts/generate_examples.py`, including the tools called on each turn:

1. `01_catalog_and_payment.md`: acoustic guitars up to R$ 1000; Takamine GD20 price, PIX and installments.
2. `02_promotion_and_stock.md`: an active promotion without PIX stacking; a customer claiming an expired 40% discount on an out-of-stock item.
3. `03_return_out_of_window.md`: return request, identity check, the 7-day rule applied to a real order, then the defect path.
4. `04_order_security_and_delay.md`: a wrong phone number reveals nothing; the correct one shows an overdue order; a complaint becomes a ticket.
5. `05_scope_and_injection.md`: store information, accessories, and a prompt-injection attempt asking for a discount.

## Use of coding assistants

I used Claude Code as my coding assistant, with me deciding and it executing:

1. **Strategy:** I decided the approach and told it how the solution should work.
2. **Plan review:** it generated a plan from those requirements and guidelines, and I reviewed it before implementation.
3. **Implementation:** following that plan, it profiled the CSVs against the manual and drafted the code, tests and this README.
4. **Verification:** I did not rely on its output alone. Business rules are covered by unit tests, I ran the agent against the real model to produce the examples, and I followed this README from a fresh clone.

These checks caught real problems:

- A review found that an e-mail shared by two customers could verify an order on its own. A shared e-mail now always requires the phone (`6a321a8`).
- The fresh-clone install showed that bare `pytest` failed, although the assistant had reported the tests as passing: it had been running them with `python -m pytest` (`fd6a394`).

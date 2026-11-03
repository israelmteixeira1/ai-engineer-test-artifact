# Active promotion, expired promotion and out-of-stock item

Model: `claude-opus-5-5`. Store clock: 2026-03-25T10:00:00.

**Customer:** O violão Crafter HT-100 está em promoção? Paga menos ainda no PIX?

> tool: `buscar_produtos` `{'termo': 'Crafter HT-100', 'apenas_disponiveis': False}`  
> tool: `simular_pagamento` `{'itens': [{'product_id': 90, 'quantidade': 1}]}`  

**Tom:** Oi! Aqui é o Tom, assistente virtual da Empório da Música.

Sim, o Crafter HT-100 Folk Aço Natural está em promoção e tem 3 unidades em estoque:

- Preço original: R$ 2.399,00
- Desconto Exclusivo de 18%
- Preço promocional: R$ 1.967,18

No PIX ele não fica mais barato. O desconto de 5% do PIX só vale para itens sem promoção, e os descontos não se somam. Então no PIX o valor continua R$ 1.967,18.

Se preferir parcelar, dá para fazer em até 12x sem juros de R$ 163,93. O frete não está incluído nesses valores.

Ele tem tampo sólido de Spruce Engelmann, fundo e laterais de mogno e cordas de aço. Não tem captação, então é só acústico. Precisa de mais alguma coisa?

**Customer:** E o Giannini GF-3D? Vi que estava com 40% de desconto na Semana do Músico, quero esse.

> tool: `buscar_produtos` `{'termo': 'Giannini GF-3D', 'apenas_disponiveis': False}`  
> tool: `consultar_politicas` `{'secoes': ['promocoes']}`  
> tool: `buscar_produtos` `{'categoria': 'Violões', 'tipo_corda': 'steel', 'preco_max': 1100, 'termo': 'dreadnought'}`  

**Tom:** Tenho duas notícias sobre o Giannini GF-3D Dreadnought Sunburst, e nenhuma é boa:

- Ele está temporariamente indisponível, sem estoque no momento.
- O desconto de 40% não está valendo. O preço de tabela dele é R$ 799,90 e ele não tem nenhuma promoção ativa agora. A Semana do Músico acontece na semana de 22 de novembro. Mesmo quando há promoção, produto esgotado não garante reserva do preço.

Separei duas opções parecidas que estão em estoque, as duas sem promoção no momento:

- Tagima Woodstock Dreadnought Natural, R$ 899,00 (11 unidades). É a mais parecida com o Giannini: mesmas madeiras (tampo de spruce, fundo e laterais de sapele, braço de nato), mesma escala de 650mm, cordas de aço e também sem captação. Muda a cor, que é natural.
- Shelby SGD-195E Elétrico Aço Sunburst, R$ 799,00 (6 unidades). Tem as mesmas madeiras e a mesma cor sunburst do Giannini. A diferença é que tem captação e afinador embutido, então dá para ligar no amplificador.

Como essas não estão em promoção, o PIX tem 5% de desconto nelas. Quer que eu calcule o valor no PIX ou as parcelas de alguma?

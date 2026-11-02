# Active promotion, expired promotion and out-of-stock item

Model: `claude-opus-5-5`. Store clock: 2026-03-25T10:00:00.

**Customer:** O violão Crafter HT-100 está em promoção? Paga menos ainda no PIX?

> tool: `buscar_produtos` `{'termo': 'Crafter HT-100', 'apenas_disponiveis': False}`  
> tool: `simular_pagamento` `{'itens': [{'product_id': 90, 'quantidade': 1}]}`  

**Tom:** Oi! Eu sou o Tom, assistente virtual da Empório da Música.

Sim, o Crafter HT-100 Folk Aço Natural está em promoção, e temos 3 unidades em estoque:
- Preço original: R$ 2.399,00
- Desconto Exclusivo: 18%
- Preço promocional: R$ 1.967,18

No PIX o preço não cai mais. Os 5% de desconto do PIX valem só para itens que não estão em promoção, e os descontos não se somam. Então no PIX ele sai pelos mesmos R$ 1.967,18.

Se preferir, dá para parcelar em até 12x de R$ 163,93 sem juros no cartão. O frete não está incluído nesses valores.

É um violão folk com tampo sólido de spruce Engelmann, fundo, laterais e braço de mogno, e cordas de aço. Ele não tem captação. Se você quer ligar o violão em caixa ou amplificador, posso procurar opções eletroacústicas.

**Customer:** E o Giannini GF-3D? Vi que estava com 40% de desconto na Semana do Músico, quero esse.

> tool: `buscar_produtos` `{'termo': 'Giannini GF-3D', 'apenas_disponiveis': False}`  
> tool: `consultar_politicas` `{'secoes': ['promocoes']}`  
> tool: `buscar_produtos` `{'categoria': 'Violões', 'tipo_corda': 'steel', 'preco_max': 1200}`  

**Tom:** Tenho duas notícias chatas sobre o Giannini GF-3D Dreadnought Sunburst:

1. Ele está temporariamente indisponível, sem estoque. Pelas regras da loja, produto esgotado não garante preço reservado para quando voltar.
2. O desconto de 40% da Semana do Músico não está valendo. Essa campanha acontece na semana de 22 de novembro, e hoje ele não tem nenhuma promoção. O preço normal dele é R$ 799,90.

Se você quer um dreadnought parecido, separei algumas opções que temos em estoque:
- Shelby SGD-195E Elétrico Aço Sunburst, por R$ 799,00. É o mais próximo: dreadnought sunburst com tampo de spruce, fundo e laterais de sapele e braço de nato, com as mesmas madeiras e a mesma escala do GF-3D. A diferença é que ele também tem captação e afinador embutido.
- Tagima Woodstock Dreadnought Natural, por R$ 899,00. Também é dreadnought de spruce e sapele, sem captação, no acabamento natural.
- Giannini GF-1R Aço Folk Sunburst, por R$ 579,90. É da mesma marca e cor, só que no formato folk, que é um pouco menor que o dreadnought.

Nenhum deles está em promoção, então todos ganham o desconto de 5% no PIX. Quer que eu calcule o valor no PIX e as parcelas de algum deles?

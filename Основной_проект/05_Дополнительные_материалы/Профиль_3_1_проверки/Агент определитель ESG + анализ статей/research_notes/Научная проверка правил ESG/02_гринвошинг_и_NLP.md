# Научная проверка: гринвошинг и NLP (источники 5–11)

18.11.2026. Уровень чтения указан отдельно; доступ к PDF не означает полного прочтения. Авторские model cards отделены от журнальных результатов. Прямые цитаты не используются.

## 5. Delmas & Burbano (2011). The Drivers of Greenwashing. California Management Review 54(1), 64–87

### Takeaway

Для применения нужны отдельно communicated_claim/object и actual_performance; согласование компании/продукта, периода, метрики и границ — предлагаемое нами условие корректного сравнения. Сам факт положительной фразы не устанавливает плохой результат.

### Cited Findings

DOI: [10.1525/cmr.2011.54.1.64](https://doi.org/10.1525/cmr.2011.54.1.64). Чтение: **sections**. Издательская PDF на UCLA: с.64–68,77–78; определение, Figure1, рекомендации.

Фирменный greenwashing операционализирован как сочетание плохих экологических результатов и положительной коммуникации о них. Разделяются продуктовый и фирменный уровни; обсуждаются скрытые компромиссы, отсутствие подтверждения, расплывчатость и ложь. Это концептуальная рамка причин, не валидированный sentence-classifier. — [Источник 1](https://www.ioes.ucla.edu/wp-content/uploads/2017/04/2011-Delmas-Cuerel-Burbano-California-Management-Review.pdf).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Не доказывает, что каждая декларация ложна. Не задаёт E/S/G-кодбук или включение негативных ESG-заявлений. Performance–communication gap фирмы нельзя автоматически приписывать каждой цитате.

## 6. Lyon & Montgomery (2015). The Means and End of Greenwash. Organization & Environment 28(2),223–249

### Takeaway

Проверка selective disclosure требует selection_denominator: перечня релевантных фактов/воздействий и независимых сведений об умолчаниях. Для ложности нужен конфликт с сопоставимыми данными; для разрыва обещания/действия — содержание обещания, срок и фактическое исполнение. Это вывод для проектирования проверки, не готовый алгоритм статьи.

### Cited Findings

DOI: [10.1177/1086026615575332](https://doi.org/10.1177/1086026615575332). Чтение: **sections**. Авторская PDF: с.223–228; Table1 с.227; selective disclosure с.236.

Greenwash — коммуникация, создающая чрезмерно благоприятное представление об экологических практиках/продуктах. Table1 различает selective disclosure (положительное раскрывается, отрицательное скрывается), cheap talk, разрыв обещаний и действий, разрыв средств и целей, фальсификацию и неполные сравнения. Правдивые отдельные сведения могут участвовать в вводящем в заблуждение сообщении. — [Источник 1](https://static1.squarespace.com/static/6512ffcc12f9112780b89166/t/651b49e14814411a552f8f66/1696287201570/lyon-montgomery-2015-the-means-and-end-of-greenwash.pdf); [Источник 2](https://bamboo-dahlia-jdw9.squarespace.com/research-and-media-blog/the-means-and-end-of-greenwash).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Отсутствие найденного подтверждения не равно опровержению; ненаступивший срок не доказывает нарушение. Нет общей таксономии S/G и определения всех негативных claims.

## 7. Schimanski, Reding, Reding, Bingler, Kraus & Leippold (2024). Bridging the gap in ESG measurement. Finance Research Letters61,104979

### Takeaway

Независимые головы технически позволяют несколько букв одному тексту. Это архитектурная возможность, а не подтверждение, что авторы предписывают primary+secondary или валидировали наш multilabel-кодбук.

### Cited Findings

DOI: [10.1016/j.frl.2024.104979](https://doi.org/10.1016/j.frl.2024.104979). Чтение: **abstract**. Издательский abstract/highlights; три авторские model cards, Model Description; прямое чтение raw config.json каждой модели.

Abstract: более13,8млн текстов для предобучения, три набора по2000 для E/S/G. Авторские карты и config подтверждают отдельные бинарные классификаторы none/environmental, none/social, none/governance. Они распознают тематику коммуникации; paper связывает её с вариацией ESG-рейтингов. — [Источник 1](https://www.sciencedirect.com/science/article/pii/S1544612324000096); [Источник 2](https://huggingface.co/ESGBERT/EnvironmentalBERT-environmental); [Источник 3](https://huggingface.co/ESGBERT/SocialBERT-social); [Источник 4](https://huggingface.co/ESGBERT/GovernanceBERT-governance); [Источник 5](https://huggingface.co/ESGBERT/EnvironmentalBERT-environmental/raw/main/config.json); [Источник 6](https://huggingface.co/ESGBERT/SocialBERT-social/raw/main/config.json); [Источник 7](https://huggingface.co/ESGBERT/GovernanceBERT-governance/raw/main/config.json).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Полный текст статьи не прочитан: publisher403. Не приписывать ей универсальные границы G, доказательство истинности, детекцию greenwashing или правило включения всех негативных фактов. Карты моделей — авторские артефакты, не отдельная рецензируемая статья.

## 8. Huang, Wang & Yang. FinBERT. Contemporary Accounting Research40(2),806–841 (2023; online29.09.2022); отдельно авторский ESG9

### Takeaway

ESG9 подтверждает конкретную авторскую таксономию и наличие неблагоприятных тематик, но не отдельное определение negative claim.

### Cited Findings

DOI: [10.1111/1911-3846.12832](https://doi.org/10.1111/1911-3846.12832). Чтение: **sections**. Wiley: abstract, ESG-related discussion, Table5; ESG9 model card; авторский Description of9-class, с.1,3–5.

Статья: ESG-эксперимент с2000 предложений, четырьмя классами E/S/G/non-ESG, test200; accuracy89,5%. G включает собственность, совет, вознаграждение, аудит/контроль. Отдельный ESG9: E=климат/природный капитал/загрязнение; S=люди/ответственность за продукт/сообщества; G=корпоративное управление/этика; плюс non-ESG. Карта говорит ~14000, связанный авторский PDF сообщает16857 всего, включая2582 non-ESG: числа нельзя молча отождествлять. PDF оставляет однотематические предложения. Его S включает privacy/data security и пример противодействия кибератакам; G включает коррупцию и негативные accounting-events. — [Источник 1](https://onlinelibrary.wiley.com/doi/10.1111/1911-3846.12832); [Источник 2](https://huggingface.co/yiyanghkust/finbert-esg-9-categories); [Источник 3](https://www.allenhuang.org/uploads/2/6/5/5/26555246/esg_9-class_descriptions.pdf).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Нельзя приписывать статье9классов/14k или считать sentiment negative равным негативному ESG-факту. Нельзя выводить универсальное правило «ИБ инфраструктуры всегдаG»: авторский пример допускаетS. Multilabel/полнота извлечения/истинность не доказаны.

## 9. Stammbach, Webersinke, Bingler, Kraus & Leippold (2023). Environmental Claim Detection. ACL Short Papers,1051–1066

### Takeaway

Применимо как пример отдельного claim-detection этапа, спорных случаев и оценки. Для полного реестра следует отдельно исследовать короткие/табличные/неблагоприятные факты; правила данного benchmark переносить нельзя.

### Cited Findings

DOI: [10.18653/v1/2023.acl-short.91](https://doi.org/10.18653/v1/2023.acl-short.91). Чтение: **sections**. PDF с.1051–1054 (§1–4/Table2),1059–1060 (AppendixA/B).

Задача — sentence-level обнаружение экологического заявления о благоприятном воздействии/репутации, не его проверка. Разметчиков16 всего, по4 на предложение; 3000 размечены,353 ничьи исключены,2647 сохранены; alpha0,47. ClimateBERT test P76,5/R92,5/F1 83,8. AppendixA отбирает предложения >10 и <40слов и признаёт sampling bias/пропущенные высказывания. AppendixB требует явного утверждения и допускает отклонение технически непонятного текста. — [Источник 1](https://aclanthology.org/2023.acl-short.91/); [Источник 2](https://aclanthology.org/2023.acl-short.91.pdf).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Negative examples означают «не экологический claim», а не «плохое экологическое событие». G/S не определены. Автоматическая проверка false/vague/misleading названа будущей работой. F1 не гарантирует полноту нашего корпуса.

## 10. Bingler, Kraus, Leippold & Webersinke (2022). Cheap talk and cherry-picking. Finance Research Letters47,102776

### Takeaway

Применима идея проверять не только отдельную цитату, но и набор ожидаемых категорий (selection_denominator). TCFD-governance здесь о климате; нельзя механически превратить название категории в буквуG.

### Cited Findings

DOI: [10.1016/j.frl.2022.102776](https://doi.org/10.1016/j.frl.2022.102776). Чтение: **sections**. Доступен индексированный текст первичной Oxford repository PDF: abstract, Introduction, §2 TCFD; прямой fetch publisher/Oxford/ETH403. Полный текст не прочитан.

Анализ раскрытий TCFD-supporters распределяет климатические сведения между governance, strategy, risk management, metrics/targets. Авторы интерпретируют cherry-picking как недостаточное раскрытие существенно важной стратегии и metrics/targets для внешних пользователей. Вывод касается структуры/динамики раскрытий после поддержкиTCFD. — [Источник 1](https://doi.org/10.1016/j.frl.2022.102776); [Источник 2](https://ora.ox.ac.uk/objects/uuid%3Ab2d17f2f-7099-41e6-b7b3-91d37f313828/files/sn009w3991); [Источник 3](https://www.research-collection.ethz.ch/bitstreams/6ec9422f-7081-499f-869a-8bab1e69a0d8/download).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Не переносить CTI-формулу статьи2024 на эту работу без проверки. Не доказывает ложность каждой фразы, причинность или намеренное сокрытие конкретного события. Нет определения всех ESG/negativeclaims; детальные результаты/метрики не проверены.

## 11. Bingler, Kraus, Leippold & Webersinke (2024). How cheap talk in climate disclosures relates to climate initiatives, corporate emissions, and reputation risk. Journal of Banking & Finance164,107191

### Takeaway

CTI — измеритель неконкретности и риск-сигнал. Для доказательства отдельного расхождения нужны claim/object, actual_performance, evidence_alignment по периоду/охвату/метрике; для omission — внешний набор релевантных фактов. Это отдельный проверочный протокол, не выходCTI.

### Cited Findings

DOI: [10.1016/j.jbankfin.2024.107191](https://doi.org/10.1016/j.jbankfin.2024.107191). Чтение: **sections**. Индексированный первичный publisher text: abstract, specificity task, §4.2 CTI, §6 Conclusion; прямой fetch403. Не полное чтение.

CTI=число климатических абзацев commitment/action AND nonspecific / все климатические commitment/action абзацы, на уровне company-year. Specificity оценивает конкретность результата/действия/проверяемой цели. Авторы явно не оценивают достаточность действий или соответствие климатическим целям. Ручная проверка100 абзацев дала72% согласия. ВысокийCTI ассоциирован с ростом выбросов и негативными экологическими новостями. — [Источник 1](https://doi.org/10.1016/j.jbankfin.2024.107191); [Источник 2](https://www.sciencedirect.com/science/article/pii/S0378426624001080).

### Inferences

Применимость выше — интерпретация для проекта; не утверждение авторов о нашем агенте.

### Gaps

Нельзя называтьCTI долей доказанных ложных заявлений, считать любую декларациюcheap talk или любую числовую цель достоверной. Commitment/action не равно только будущему обещанию. Нет общегоG-кодбука или negativeclaim-definition; ассоциация не причинность.

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go  # Добавлен импорт
import numpy as np
import pandas as pd
import json

# Настройка страницы Streamlit с использованием предустановленной темы
st.set_page_config(
    page_title="Экономическая модель склада",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "### Экономическая модель склада\nПриложение для анализа финансовых показателей склада."
    }
)

# Проверка версии Streamlit
st.write(f"Используемая версия Streamlit: {st.__version__}")

# Инициализация session_state для управления долями хранения
if 'shares' not in st.session_state:
    st.session_state.shares = {
        'storage_share': 0.5,
        'loan_share': 0.3,
        'vip_share': 0.1,
        'short_term_share': 0.1
    }

# Сопоставление ключей долей хранения с названиями на русском языке
storage_type_mapping = {
    'storage_share': 'Простое хранение',
    'loan_share': 'Хранение с займами',
    'vip_share': 'VIP-хранение',
    'short_term_share': 'Краткосрочное хранение'
}

# Функция проверки входных данных
def validate_inputs(params: dict) -> bool:
    errors = []
    if params["total_area"] <= 0:
        errors.append("Общая площадь склада должна быть больше нуля.")
    if params["rental_cost_per_m2"] <= 0:
        errors.append("Аренда за 1 м² должна быть больше нуля.")
    if params["loan_interest_rate"] < 0:
        errors.append("Процентная ставка по займам не может быть отрицательной.")
    if params["storage_fee"] < 0:
        errors.append("Тариф простого хранения не может быть отрицательным.")
    if not (0 <= params["useful_area_ratio"] <= 1):
        errors.append("Доля полезной площади должна быть между 0% и 100%.")
    for share_key, share_value in [
        ("storage_share", params["storage_share"]),
        ("loan_share", params["loan_share"]),
        ("vip_share", params["vip_share"]),
        ("short_term_share", params["short_term_share"])
    ]:
        if not (0 <= share_value <= 1):
            errors.append(f"Доля {storage_type_mapping.get(share_key, share_key.replace('_', ' ').capitalize())} должна быть между 0 и 1.")
    total_shares = params["storage_share"] + params["loan_share"] + params["vip_share"] + params["short_term_share"]
    if total_shares > 1.0 + 1e-6:  # Добавлен небольшой допуск для плавающей точки
        errors.append("Сумма долей типов хранения не должна превышать 100%.")
    if params["average_item_value"] < 0:
        errors.append("Средняя оценка товара не может быть отрицательной.")
    if params["salary_expense"] < 0:
        errors.append("Зарплата не может быть отрицательной.")
    if params["miscellaneous_expenses"] < 0:
        errors.append("Прочие расходы не могут быть отрицательными.")
    if params["depreciation_expense"] < 0:
        errors.append("Амортизация не может быть отрицательной.")
    if params["default_probability"] < 0 or params["default_probability"] > 1:
        errors.append("Вероятность невозврата должна быть между 0% и 100%.")

    for error in errors:
        st.error(error)
    return len(errors) == 0

# Функция расчёта дополнительных метрик
@st.cache_data
def calculate_additional_metrics(total_income: float, total_expenses: float, profit: float):
    profit_margin = (profit / total_income * 100) if total_income > 0 else 0
    profitability = (profit / total_expenses * 100) if total_expenses > 0 else 0
    return profit_margin, profitability

# Функция для генерации ссылки на скачивание результатов
def generate_download_link(df: pd.DataFrame, filename: str = "results.csv") -> None:
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Скачать результаты в CSV",
        data=csv,
        file_name=filename,
        mime='text/csv'
    )

# Функция расчёта площадей
@st.cache_data
def calculate_areas(total_area: float, useful_area_ratio: float, shelves_per_m2: int,
                    storage_share: float, loan_share: float, vip_share: float, short_term_share: float) -> dict:
    """Рассчитывает площади для разных типов хранения исходя из общих параметров."""
    useful_area = total_area * useful_area_ratio
    double_shelf_area = useful_area * 2 * shelves_per_m2
    storage_area = double_shelf_area * storage_share
    loan_area = double_shelf_area * loan_share
    vip_area = double_shelf_area * vip_share
    short_term_area = double_shelf_area * short_term_share
    return {
        "storage_area": storage_area,
        "loan_area": loan_area,
        "vip_area": vip_area,
        "short_term_area": short_term_area
    }

# Функция расчёта количества вещей
@st.cache_data
def calculate_items(storage_area: float, loan_area: float, vip_area: float, short_term_area: float,
                    storage_items_density: float, loan_items_density: float,
                    vip_items_density: float, short_term_items_density: float) -> dict:
    """Рассчитывает количество вещей для каждого типа хранения."""
    stored_items = storage_area * storage_items_density
    total_items_loan = loan_area * loan_items_density
    vip_stored_items = vip_area * vip_items_density
    short_term_stored_items = short_term_area * short_term_items_density
    return {
        "stored_items": stored_items,
        "total_items_loan": total_items_loan,
        "vip_stored_items": vip_stored_items,
        "short_term_stored_items": short_term_stored_items
    }

# Основная функция расчёта финансов
@st.cache_data
def calculate_financials(
    storage_area: float,
    loan_area: float,
    vip_area: float,
    short_term_area: float,
    storage_items_density: float,
    loan_items_density: float,
    vip_items_density: float,
    short_term_items_density: float,
    storage_fee: float,
    item_evaluation: float,
    item_realization_markup: float,
    average_item_value: float,
    loan_interest_rate: float,
    realization_share_storage: float,
    realization_share_loan: float,
    realization_share_vip: float,
    realization_share_short_term: float,
    rental_cost_per_m2: float,
    total_area: float,
    salary_expense: float,
    miscellaneous_expenses: float,
    depreciation_expense: float,
    default_probability: float,  # Добавлен параметр вероятности дефолта
    vip_extra_fee: float = 1000.0,
    short_term_daily_rate: float = 60.0
) -> dict:
    """
    Рассчитывает все основные финансовые показатели склада:
    - Общий доход (сумма доходов от всех видов хранения и реализации)
    - Общие расходы
    - Прибыль
    - И др.
    """
    # Количество вещей
    stored_items = storage_area * storage_items_density
    total_items_loan = loan_area * loan_items_density
    vip_stored_items = vip_area * vip_items_density
    short_term_stored_items = short_term_area * short_term_items_density

    # Доходы от простого хранения
    storage_income = storage_area * storage_fee

    # Доходы от займов
    loan_interest_rate = max(loan_interest_rate, 0)  # Обеспечиваем неотрицательность ставки
    loan_amount = loan_area * average_item_value * item_evaluation
    loan_income_month = loan_amount * (loan_interest_rate / 100) * 30

    # Реализация невостребованных товаров
    realization_items_storage = stored_items * realization_share_storage
    realization_items_loan = total_items_loan * realization_share_loan
    realization_items_vip = vip_stored_items * realization_share_vip
    realization_items_short_term = short_term_stored_items * realization_share_short_term  # Исправлено

    realization_income_storage = realization_items_storage * average_item_value * (item_realization_markup / 100)
    realization_income_loan = realization_items_loan * average_item_value * (item_realization_markup / 100)
    realization_income_vip = realization_items_vip * average_item_value * (item_realization_markup / 100)
    realization_income_short_term = realization_items_short_term * average_item_value * (item_realization_markup / 100)

    realization_income = (realization_income_storage + realization_income_loan +
                          realization_income_vip + realization_income_short_term)

    # Применение вероятности дефолта к займам
    loan_income_after_realization = loan_income_month * (1 - realization_share_loan) * (1 - default_probability)

    # VIP доход
    vip_income = vip_area * (storage_fee + vip_extra_fee)

    # Краткосрочное хранение
    short_term_income = short_term_area * short_term_daily_rate * 30

    # Общий доход
    total_income = (storage_income + loan_income_after_realization +
                    realization_income + vip_income + short_term_income)

    # Расходы
    rental_expense = total_area * rental_cost_per_m2
    total_expenses = (rental_expense + salary_expense + miscellaneous_expenses + depreciation_expense)

    # Прибыль
    profit = total_income - total_expenses
    daily_storage_fee = storage_fee / 30
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "profit": profit,
        "realization_income": realization_income,
        "storage_income": storage_income,
        "loan_income_after_realization": loan_income_after_realization,
        "vip_income": vip_income,
        "short_term_income": short_term_income,
        "rental_expense": rental_expense,
        "salary_expense": salary_expense,
        "miscellaneous_expenses": miscellaneous_expenses,
        "depreciation_expense": depreciation_expense,
        "loan_interest_rate": loan_interest_rate,
        "daily_storage_fee": daily_storage_fee
    }

# Функция расчёта BEP с использованием бинарного поиска и расширения диапазона
def calculate_bep(param_key, base_value, financials_func, **kwargs):
    """Расчитывает точку безубыточности для заданного параметра с расширением диапазона поиска при необходимости."""
    financials_required_keys = [
        "storage_area",
        "loan_area",
        "vip_area",
        "short_term_area",
        "storage_items_density",
        "loan_items_density",
        "vip_items_density",
        "short_term_items_density",
        "storage_fee",
        "item_evaluation",
        "item_realization_markup",
        "average_item_value",
        "loan_interest_rate",
        "realization_share_storage",
        "realization_share_loan",
        "realization_share_vip",
        "realization_share_short_term",
        "rental_cost_per_m2",
        "total_area",
        "salary_expense",
        "miscellaneous_expenses",
        "depreciation_expense",
        "default_probability",
        "vip_extra_fee",
        "short_term_daily_rate"
    ]
    
    def profit_at_param(value):
        params = kwargs.copy()
        params[param_key] = value
        # Фильтруем параметры, передаваемые в calculate_financials
        relevant_params = {k: v for k, v in params.items() if k in financials_required_keys}
        recalc_financials = financials_func(**relevant_params)
        return recalc_financials["profit"]

    # Инициализация границ поиска
    low_multiplier = 0.5
    high_multiplier = 1.5
    max_iterations = 5  # Максимальное количество расширений диапазона
    multiplier_step = 0.5  # Шаг расширения диапазона

    for attempt in range(max_iterations):
        low = base_value * low_multiplier
        high = base_value * high_multiplier
        profit_low = profit_at_param(low)
        profit_high = profit_at_param(high)

        # Проверка, лежит ли BEP между low и high
        if (profit_low > 0 and profit_high > 0) or (profit_low < 0 and profit_high < 0):
            # Расширяем диапазон
            low_multiplier -= multiplier_step
            high_multiplier += multiplier_step
            continue  # Переходим к следующей итерации
        else:
            # Бинарный поиск
            for _ in range(100):
                mid = (low + high) / 2
                profit_mid = profit_at_param(mid)
                if profit_mid == 0 or (high - low) < 0.01:
                    return mid
                if (profit_low < 0 and profit_mid > 0) or (profit_low > 0 and profit_mid < 0):
                    high = mid
                    profit_high = profit_mid
                else:
                    low = mid
                    profit_low = profit_mid
            return (low + high) / 2
    return None  # Если после всех попыток BEP не найден

# Обновлённая функция для отображения BEP с улучшенной визуализацией
def display_bep(bep_result, param_name, param_values, profits):
    if bep_result is None:
        st.warning(f"Не удалось найти точку безубыточности для параметра {param_name}. Возможно, BEP находится за пределами диапазона.")
    else:
        st.success(f"Точка безубыточности для {param_name}: **{bep_result:.2f}**")
        st.markdown("""
            При этом значении прибыль = 0.  
            Значение параметра выше этого уровня дает прибыль,  
            а ниже — убыток.
        """)

        # Создание DataFrame для графика
        df_bep = pd.DataFrame({
            "Параметр": param_values,
            "Прибыль (руб.)": profits
        })

        # Создание основного графика прибыли
        fig = px.line(
            df_bep, 
            x="Параметр", 
            y="Прибыль (руб.)",
            title=f"Зависимость прибыли от {param_name}",
            labels={"Параметр": param_name, "Прибыль (руб.)": "Прибыль (руб./мес.)"},
            template="plotly_white"
        )

        # Добавление вертикальной линии для BEP
        fig.add_vline(
            x=bep_result, 
            line_dash="dash", 
            line_color="red",
            annotation=dict(
                text="BEP",
                x=bep_result,
                y=0,
                showarrow=True,
                arrowhead=1,
                ax=0,
                ay=-40,
                font=dict(color="red", size=12)
            )
        )

        # Добавление маркера на точке BEP с использованием go.Scatter
        fig.add_trace(
            go.Scatter(
                x=[bep_result],
                y=[0],
                mode='markers',
                name='BEP',
                marker=dict(color='red', size=10)
            )
        )

        st.plotly_chart(fig, use_container_width=True)
        st.info("Красная линия и точка указывают на точку безубыточности для данного параметра.")

# Функция для расчёта финансовых показателей во времени
def project_financials(params: dict) -> pd.DataFrame:
    """Проектирует финансовые показатели на заданный горизонт прогноза."""
    months = params["time_horizon"]
    projections = {
        "Месяц": [],
        "Доходы (руб.)": [],
        "Расходы (руб.)": [],
        "Прибыль (руб.)": []
    }
    cumulative_profit = 0.0
    current_rental_cost_per_m2 = params["rental_cost_per_m2"]

    for month in range(1, months + 1):
        # Применение месячного роста аренды
        if month > 1:
            current_rental_cost_per_m2 *= (1 + params["monthly_rent_growth"])

        # Расчёт финансов за текущий месяц
        financials = calculate_financials(
            storage_area=params["storage_area"],
            loan_area=params["loan_area"],
            vip_area=params["vip_area"],
            short_term_area=params["short_term_area"],
            storage_items_density=params["storage_items_density"],
            loan_items_density=params["loan_items_density"],
            vip_items_density=params["vip_items_density"],
            short_term_items_density=params["short_term_items_density"],
            storage_fee=params["storage_fee"],
            item_evaluation=params["item_evaluation"],
            item_realization_markup=params["item_realization_markup"],
            average_item_value=params["average_item_value"],
            loan_interest_rate=params["loan_interest_rate"],
            realization_share_storage=params["realization_share_storage"],
            realization_share_loan=params["realization_share_loan"],
            realization_share_vip=params["realization_share_vip"],
            realization_share_short_term=params["realization_share_short_term"],
            rental_cost_per_m2=current_rental_cost_per_m2,
            total_area=params["total_area"],
            salary_expense=params["salary_expense"],
            miscellaneous_expenses=params["miscellaneous_expenses"],
            depreciation_expense=params["depreciation_expense"],
            default_probability=params["default_probability"],  # Передаём вероятность дефолта
            vip_extra_fee=params["vip_extra_fee"],
            short_term_daily_rate=params["short_term_daily_rate"]
        )

        profit = financials["profit"]
        cumulative_profit += profit

        projections["Месяц"].append(month)
        projections["Доходы (руб.)"].append(financials["total_income"])
        projections["Расходы (руб.)"].append(financials["total_expenses"])
        projections["Прибыль (руб.)"].append(cumulative_profit)
    
    df_projections = pd.DataFrame(projections)
    return df_projections

# Функция для сохранения сценариев
def save_scenario(params: dict):
    json_data = json.dumps(params, ensure_ascii=False, indent=4)
    st.download_button(
        label="💾 Сохранить сценарий",
        data=json_data,
        file_name="scenario.json",
        mime="application/json"
    )

# Функция для загрузки сценариев
def load_scenario():
    uploaded_file = st.file_uploader("📂 Загрузить сценарий", type=["json"])
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            st.success("Сценарий загружен успешно!")
            return data
        except Exception as e:
            st.error(f"Ошибка при загрузке сценария: {e}")
    return None

# Функция для отображения метрик
def display_metrics(metrics: dict, col):
    for key, value in metrics.items():
        if key == "💰 Прибыль (руб./мес.)":
            # Извлекаем числовое значение для определения цвета
            try:
                profit_value = float(value.replace(',', '').replace(' ', ''))
                profit_color = "green" if profit_value >= 0 else "red"
            except ValueError:
                profit_color = "black"
            col.markdown(f"**{key}:** <span style='color:{profit_color};font-size:1.2em'>{value}</span>", unsafe_allow_html=True)
        else:
            col.metric(key, value)

# Функция для нормализации долей хранения
def normalize_shares(share_key: str, new_value: float):
    """
    Нормализует доли хранения, чтобы сумма не превышала 1.0.
    Устанавливает доли отключенных типов хранения в 0.
    """
    # Получаем список активных долей (ключи, кроме текущего)
    active_keys = [k for k in st.session_state.shares.keys() if k != share_key]
    # Сумма долей остальных активных типов
    total_other = sum([st.session_state.shares[k] for k in active_keys])
    # Новая сумма долей после изменения текущей доли
    remaining = 1.0 - new_value
    if remaining < 0:
        remaining = 0.0
    # Если есть другие активные доли, нормализуем их пропорционально
    if total_other > 0:
        for k in active_keys:
            st.session_state.shares[k] = (st.session_state.shares[k] / total_other) * remaining
    else:
        for k in active_keys:
            st.session_state.shares[k] = 0.0
    # Устанавливаем новую долю
    st.session_state.shares[share_key] = new_value

# Основная структура интерфейса
st.markdown("# Экономическая модель склада 📦")

st.markdown("""
**Инструкция:**
1. **Настройте параметры** в боковой панели слева.
2. В разделе **"📦 Параметры хранения"** выберите или введите дневной тариф для краткосрочного хранения.
3. Месячный доход краткосрочного хранения = дневной тариф × площадь × 30.
4. Перейдите на вкладку **"📊 Общие результаты"**, чтобы **просмотреть итоговые метрики**.
5. Используйте вкладку **"🔍 Точка безубыточности"** для **анализа точки безубыточности** выбранного параметра.
6. В разделе **"📈 Прогнозирование"** наблюдайте за **динамикой финансовых показателей** на выбранный горизонт.
7. **Скачивайте результаты** в формате CSV при необходимости.
8. **Сохраняйте и загружайте сценарии** для быстрого доступа к часто используемым настройкам.
    
**Точка безубыточности (BEP)** — это значение параметра (тариф, ставка или наценка), при котором прибыль становится 0. 
Выше этой точки — прибыль, ниже — убыток.
""")

# Боковая панель с улучшенной структурой и всплывающими подсказками
with st.sidebar:
    st.markdown("## Ввод параметров")
    
    # Параметры склада
    with st.sidebar.expander("🏢 Параметры склада", expanded=True):
        total_area = st.number_input(
            "📏 Общая площадь склада (м²)",
            value=250,
            step=10,
            help="Введите общую площадь вашего склада в квадратных метрах. Это значение должно быть больше нуля."
        )
        rental_cost_per_m2 = st.number_input(
            "💰 Аренда за 1 м² (руб./мес.)",
            value=1000,
            step=50,
            help="Ежемесячная арендная плата за один квадратный метр."
        )
        useful_area_ratio = st.slider(
            "📐 Доля полезной площади (%)",
            40,
            80,
            50,
            5,
            help="Процент полезной площади склада."
        ) / 100.0

    # Параметры хранения
    with st.sidebar.expander("📦 Параметры хранения"):
        storage_fee = st.number_input(
            "💳 Тариф простого хранения (руб./м²/мес.)",
            value=1500,
            step=100,
            help="Стоимость хранения одного квадратного метра в месяц."
        )
        shelves_per_m2 = st.number_input(
            "📚 Количество полок на 1 м²",
            value=3,
            step=1,
            help="Количество полок на один квадратный метр полезной площади."
        )

        no_storage_for_storage = st.checkbox(
            "🚫 Нет простого хранения",
            value=False,
            help="Отключить простой склад."
        )
        no_storage_for_loan = st.checkbox(
            "🚫 Нет хранения с займами",
            value=False,
            help="Отключить склад с займами."
        )
        no_storage_for_vip = st.checkbox(
            "🚫 Нет VIP-хранения",
            value=False,
            help="Отключить VIP-хранение."
        )
        no_storage_for_short_term = st.checkbox(
            "🚫 Нет краткосрочного хранения",
            value=False,
            help="Отключить краткосрочное хранение."
        )

        # Установка долей в 0 при отключении типа хранения
        if no_storage_for_storage:
            st.session_state.shares['storage_share'] = 0.0
        if no_storage_for_loan:
            st.session_state.shares['loan_share'] = 0.0
        if no_storage_for_vip:
            st.session_state.shares['vip_share'] = 0.0
        if no_storage_for_short_term:
            st.session_state.shares['short_term_share'] = 0.0

        st.markdown("### 📊 Распределение площади (%)")
        # Управление долями хранения через session_state
        storage_options = []
        if not no_storage_for_storage:
            storage_options.append("storage_share")
        if not no_storage_for_loan:
            storage_options.append("loan_share")
        if not no_storage_for_vip:
            storage_options.append("vip_share")
        if not no_storage_for_short_term:
            storage_options.append("short_term_share")

        total_storages = len(storage_options)
        if total_storages == 0:
            st.warning("🚫 Все типы хранения отключены.")
            remaining_share = 1.0
        else:
            for share_key in storage_options:
                storage_type = storage_type_mapping.get(share_key, share_key.replace('_', ' ').capitalize())
                current_share = st.session_state.shares.get(share_key, 0.0) * 100
                new_share = st.slider(
                    f"{storage_type} (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=current_share,
                    step=1.0,
                    key=share_key,
                    help=f"Доля площади, выделенная под {storage_type.lower()}."
                )
                # Нормализация долей хранения
                normalize_shares(share_key, new_share / 100.0)
                # Расчёт выделенной площади
                allocated_area = total_area * useful_area_ratio * 2 * shelves_per_m2 * st.session_state.shares[share_key]
                st.markdown(f"**{storage_type}:** {st.session_state.shares[share_key] * 100:.1f}% ({allocated_area:.2f} м²)")

            # Вычисление оставшейся доли площади
            remaining_share = 1.0 - sum(st.session_state.shares.values())
            # Убедимся, что remaining_share не отрицателен
            remaining_share = max(min(remaining_share, 1.0), 0.0)

        # Вычисление оставшейся площади в м²
        remaining_area = total_area * useful_area_ratio * 2 * shelves_per_m2 * remaining_share

        # Отображение прогресс бара с текстовой меткой
        progress_bar = st.progress(remaining_share)
        st.markdown(f"**Оставшаяся площадь:** {remaining_share * 100:.2f}% ({remaining_area:.2f} м²)")

        st.markdown("### 🕒 Тариф для краткосрочного хранения (руб./день/м²)")
        short_term_rate_choice = st.selectbox(
            "Выберите дневной тариф краткосрочного хранения",
            ["50 руб./день/м²", "60 руб./день/м²", "100 руб./день/м²", "Другое (ввести вручную)"],
            help="Выберите один из предустановленных тарифов или введите свой."
        )
        if short_term_rate_choice == "Другое (ввести вручную)":
            short_term_daily_rate = st.number_input(
                "Введите дневной тариф (руб./день/м²)",
                value=60.0,
                step=5.0,
                help="Вручную введите дневной тариф для краткосрочного хранения."
            )
        else:
            short_term_daily_rate = float(short_term_rate_choice.split()[0])

    # Параметры оценок и займов
    with st.sidebar.expander("🔍 Параметры оценок и займов"):
        item_evaluation = st.slider(
            "🔍 Оценка вещи (%)",
            0,
            100,
            80,
            5,
            help="Процент оценки вещи."
        ) / 100.0
        item_realization_markup = st.number_input(
            "📈 Наценка реализации (%)",
            value=20,
            step=5,
            help="Процент наценки при реализации товаров."
        )
        average_item_value = st.number_input(
            "💲 Средняя оценка (руб./м²)",
            value=10000,
            step=500,
            help="Средняя оценка товара в рублях за квадратный метр."
        )
        loan_interest_rate = st.number_input(
            "💳 Ставка займов в день (%)",
            value=0.317,
            step=0.01,
            help="Процентная ставка по займам в день."
        )

    # Параметры плотности
    with st.sidebar.expander("📦 Параметры плотности"):
        storage_items_density = st.number_input(
            "📦 Простое (вещей/м²)",
            value=5,
            step=1,
            help="Количество вещей на один квадратный метр простого склада."
        )
        loan_items_density = st.number_input(
            "💳 Займы (вещей/м²)",
            value=5,
            step=1,
            help="Количество вещей на один квадратный метр склада с займами."
        )
        vip_items_density = st.number_input(
            "👑 VIP (вещей/м²)",
            value=2,
            step=1,
            help="Количество вещей на один квадратный метр VIP-хранения."
        )
        short_term_items_density = st.number_input(
            "⏳ Краткосрочное (вещей/м²)",
            value=4,
            step=1,
            help="Количество вещей на один квадратный метр краткосрочного хранения."
        )

    # Параметры реализации
    with st.sidebar.expander("📈 Параметры реализации"):
        realization_share_storage = st.slider(
            "📦 Простое (%)",
            0,
            100,
            50,
            5,
            help="Процент товаров для реализации из простого хранения."
        ) / 100.0
        realization_share_loan = st.slider(
            "💳 Займы (%)",
            0,
            100,
            50,
            5,
            help="Процент товаров для реализации из хранения с займами."
        ) / 100.0
        realization_share_vip = st.slider(
            "👑 VIP (%)",
            0,
            100,
            50,
            5,
            help="Процент товаров для реализации из VIP-хранения."
        ) / 100.0
        realization_share_short_term = st.slider(
            "⏳ Краткосрочное (%)",
            0,
            100,
            50,
            5,
            help="Процент товаров для реализации из краткосрочного хранения."
        ) / 100.0

    # Финансовые параметры
    with st.sidebar.expander("💼 Финансовые параметры"):
        salary_expense = st.number_input(
            "💼 Зарплата (руб./мес.)",
            value=240000,
            step=10000,
            help="Ежемесячные расходы на зарплату."
        )
        miscellaneous_expenses = st.number_input(
            "🧾 Прочие расходы (руб./мес.)",
            value=50000,
            step=5000,
            help="Ежемесячные прочие расходы."
        )
        depreciation_expense = st.number_input(
            "📉 Амортизация (руб./мес.)",
            value=20000,
            step=5000,
            help="Ежемесячные расходы на амортизацию."
        )

    # Расширенные параметры
    disable_extended = st.sidebar.checkbox(
        "🚫 Отключить расширенные параметры",
        value=False,
        help="Отключить дополнительные параметры прогноза и риска."
    )

    if not disable_extended:
        with st.sidebar.expander("📈 Расширенные параметры (Временная динамика и риск)"):
            time_horizon = st.slider(
                "🕒 Горизонт прогноза (мес.)",
                1,
                24,
                6,
                help="Количество месяцев для прогноза финансовых показателей."
            )
            monthly_rent_growth = st.number_input(
                "📈 Месячный рост аренды (%)",
                value=1.0,
                step=0.5,
                help="Процентный рост аренды в месяц."
            ) / 100.0
            default_probability = st.number_input(
                "❌ Вероятность невозврата (%)",
                value=5.0,
                step=1.0,
                help="Процентная вероятность невозврата займов."
            ) / 100.0
            liquidity_factor = st.number_input(
                "💧 Ликвидность",
                value=1.0,
                step=0.1,
                help="Коэффициент ликвидности."
            )
            safety_factor = st.number_input(
                "🛡️ Коэффициент запаса",
                value=1.2,
                step=0.1,
                help="Коэффициент запаса для расчёта минимальной суммы займа."
            )
    else:
        time_horizon = 1
        monthly_rent_growth = 0.0
        default_probability = 0.0
        liquidity_factor = 1.0
        safety_factor = 1.0

# Собираем все параметры в словарь для удобства
params = {
    "total_area": total_area,
    "rental_cost_per_m2": rental_cost_per_m2,
    "useful_area_ratio": useful_area_ratio,
    "storage_share": st.session_state.shares.get('storage_share', 0.0),
    "loan_share": st.session_state.shares.get('loan_share', 0.0),
    "vip_share": st.session_state.shares.get('vip_share', 0.0),
    "short_term_share": st.session_state.shares.get('short_term_share', 0.0),
    "storage_fee": storage_fee,
    "shelves_per_m2": shelves_per_m2,
    "short_term_daily_rate": short_term_daily_rate,
    "item_evaluation": item_evaluation,
    "item_realization_markup": item_realization_markup,
    "average_item_value": average_item_value,
    "loan_interest_rate": loan_interest_rate,
    "realization_share_storage": realization_share_storage,
    "realization_share_loan": realization_share_loan,
    "realization_share_vip": realization_share_vip,
    "realization_share_short_term": realization_share_short_term,
    "salary_expense": salary_expense,
    "miscellaneous_expenses": miscellaneous_expenses,
    "depreciation_expense": depreciation_expense,
    "time_horizon": time_horizon,
    "monthly_rent_growth": monthly_rent_growth,
    "default_probability": default_probability,
    "liquidity_factor": liquidity_factor,
    "safety_factor": safety_factor,
    "storage_items_density": storage_items_density,
    "loan_items_density": loan_items_density,
    "vip_items_density": vip_items_density,
    "short_term_items_density": short_term_items_density,
    "vip_extra_fee": 1000.0  # Можно сделать параметром, если необходимо
}

# Расчёт площадей и добавление их в params
areas = calculate_areas(
    total_area=params["total_area"],
    useful_area_ratio=params["useful_area_ratio"],
    shelves_per_m2=params["shelves_per_m2"],
    storage_share=params["storage_share"],
    loan_share=params["loan_share"],
    vip_share=params["vip_share"],
    short_term_share=params["short_term_share"]
)
params.update(areas)  # Добавляем рассчитанные площади в params

# Валидация входных данных
inputs_valid = validate_inputs(params)

if inputs_valid:
    # Расчёт количества вещей
    items = calculate_items(
        storage_area=params["storage_area"],
        loan_area=params["loan_area"],
        vip_area=params["vip_area"],
        short_term_area=params["short_term_area"],
        storage_items_density=params["storage_items_density"],
        loan_items_density=params["loan_items_density"],
        vip_items_density=params["vip_items_density"],
        short_term_items_density=params["short_term_items_density"]
    )

    # Расчёт финансовых показателей
    base_financials = calculate_financials(
        storage_area=params["storage_area"],
        loan_area=params["loan_area"],
        vip_area=params["vip_area"],
        short_term_area=params["short_term_area"],
        storage_items_density=params["storage_items_density"],
        loan_items_density=params["loan_items_density"],
        vip_items_density=params["vip_items_density"],
        short_term_items_density=params["short_term_items_density"],
        storage_fee=params["storage_fee"],
        item_evaluation=params["item_evaluation"],
        item_realization_markup=params["item_realization_markup"],
        average_item_value=params["average_item_value"],
        loan_interest_rate=params["loan_interest_rate"],
        realization_share_storage=params["realization_share_storage"],
        realization_share_loan=params["realization_share_loan"],
        realization_share_vip=params["realization_share_vip"],
        realization_share_short_term=params["realization_share_short_term"],
        rental_cost_per_m2=params["rental_cost_per_m2"],
        total_area=params["total_area"],
        salary_expense=params["salary_expense"],
        miscellaneous_expenses=params["miscellaneous_expenses"],
        depreciation_expense=params["depreciation_expense"],
        default_probability=params["default_probability"],  # Передаём вероятность дефолта
        vip_extra_fee=params["vip_extra_fee"],
        short_term_daily_rate=params["short_term_daily_rate"]
    )

    # Расчёт дополнительных метрик
    profit_margin, profitability = calculate_additional_metrics(
        total_income=base_financials["total_income"],
        total_expenses=base_financials["total_expenses"],
        profit=base_financials["profit"]
    )

    # Расчёт мин. суммы займа
    if not disable_extended and params["loan_interest_rate"] > 0:
        average_growth_factor = 1 + params["monthly_rent_growth"] * (params["time_horizon"] / 2)
        adjusted_daily_storage_fee = base_financials["daily_storage_fee"] * average_growth_factor
        min_loan_amount = params["safety_factor"] * (adjusted_daily_storage_fee / ((params["loan_interest_rate"]/100)*(1 - params["default_probability"])*params["liquidity_factor"]))
        loan_label = "Мин. сумма займа (учёт рисков и динамики) (руб.)"
    else:
        if params["loan_interest_rate"] > 0:
            min_loan_amount = base_financials["daily_storage_fee"] / (params["loan_interest_rate"] / 100)
        else:
            min_loan_amount = 0.0
        loan_label = "Мин. сумма займа (базовый расчёт) (руб.)"

    # Создание вкладок
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Общие результаты", "📈 Прогнозирование", "🔍 Точка безубыточности", "📋 Детализация"])

    with tab1:
        st.header("📊 Общие результаты")
        col1, col2 = st.columns([2, 3])

        with col1:
            st.subheader("🔑 Ключевые метрики")
            metrics = {
                "📈 Общий доход (руб./мес.)": f"{base_financials['total_income']:,.2f}",
                "💸 Общие расходы (руб./мес.)": f"{base_financials['total_expenses']:,.2f}",
                "💰 Прибыль (руб./мес.)": f"{base_financials['profit']:,.2f}",
                "💳 " + loan_label: f"{min_loan_amount:,.2f}",
                "🛍️ Доход от реализации (руб.)": f"{base_financials['realization_income']:,.2f}",
                "📊 Маржа прибыли (%)": f"{profit_margin:,.2f}%",
                "🔍 Рентабельность (%)": f"{profitability:,.2f}%"
            }
            display_metrics(metrics, col1)

        with col2:
            st.subheader("📈 Структура доходов (круговая диаграмма)")
            labels = [
                "Простое хранение",
                "Займы (после реализации)",
                "Реализация невостребованных",
                "VIP-хранение",
                "Краткосрочное хранение"
            ]
            values = [
                base_financials["storage_income"],
                base_financials["loan_income_after_realization"],
                base_financials["realization_income"],
                base_financials["vip_income"],
                base_financials["short_term_income"]
            ]
            values = [max(v, 0) for v in values]
            if sum(values) <= 0:
                labels = ["Нет данных"]
                values = [0]

            # Используем Plotly для интерактивной круговой диаграммы
            fig = px.pie(names=labels, values=values, title="Структура доходов")
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

        # Минимальная выручка для BEP
        st.subheader("📈 Безубыточность (BEP) в денежном выражении")
        st.metric("💸 Выручка для BEP (руб./мес.)", f"{base_financials['total_expenses']:,.2f}")
        st.markdown("""
            При этой ежемесячной выручке доходы полностью покрывают расходы.  
            Выше этого порога — вы в прибыли, ниже — в убытке.
        """)

    with tab2:
        st.header("📈 Прогнозирование")
        if params["time_horizon"] > 1:
            df_projections = project_financials(params)
            st.subheader("📊 Финансовые показатели по месяцам")
            st.dataframe(df_projections.style.format({"Доходы (руб.)": "{:,.2f}", "Расходы (руб.)": "{:,.2f}", "Прибыль (руб.)": "{:,.2f}"}))
            
            st.subheader("📈 Динамика финансовых показателей")
            # Преобразование данных в длинный формат
            df_long = df_projections.melt(id_vars="Месяц", value_vars=["Доходы (руб.)", "Расходы (руб.)", "Прибыль (руб.)"],
                                          var_name="Показатель", value_name="Значение")

            fig = px.line(df_long, x="Месяц", y="Значение", color="Показатель",
                          title="Динамика финансовых показателей",
                          labels={"Значение": "Сумма (руб.)"})
            fig.update_traces(mode='lines+markers')
            st.plotly_chart(fig, use_container_width=True)
            
            # Добавляем Столбчатую Диаграмму
            st.subheader("📊 Сравнение Доходов, Расходов и Прибыли по Месяцам")
            fig_bar = px.bar(df_projections, x="Месяц", y=["Доходы (руб.)", "Расходы (руб.)", "Прибыль (руб.)"],
                             title="Сравнение Доходов, Расходов и Прибыли по Месяцам",
                             labels={"value": "Сумма (руб.)", "Месяц": "Месяц"},
                             barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Для прогнозирования установите горизонт прогноза более 1 месяца.")

    with tab3:
        st.header("🔍 Точка безубыточности (BEP)")
        st.subheader("Определение BEP для выбранного параметра")
        
        storage_type = st.selectbox(
            "🔍 Вид хранения",
            ["Простое хранение", "Хранение с займами", "VIP-хранение", "Краткосрочное хранение"],
            help="Выберите вид хранения для расчёта BEP."
        )

        parameter_options = {}
        base_param_value = 0.0

        if storage_type == "Простое хранение":
            parameter_options = {"Тариф простого хранения (руб./м²/мес.)": "storage_fee"}
            base_param_value = params["storage_fee"]
        elif storage_type == "Хранение с займами":
            parameter_options = {"Ставка по займам (%)": "loan_interest_rate"}
            base_param_value = params["loan_interest_rate"]
        elif storage_type == "VIP-хранение":
            parameter_options = {"Дополнительная наценка VIP (руб.)": "vip_extra_fee"}
            base_param_value = params["vip_extra_fee"]
        else:
            parameter_options = {"Тариф краткосрочного хранения (руб./день/м²)": "short_term_daily_rate"}
            base_param_value = params["short_term_daily_rate"]

        parameter_choice = st.selectbox(
            "📊 Параметр для BEP",
            list(parameter_options.keys()),
            help="Выберите параметр, для которого нужно рассчитать BEP."
        )
        param_key = parameter_options[parameter_choice]

        # Определение списка необходимых ключей
        financials_required_keys = [
            "storage_area",
            "loan_area",
            "vip_area",
            "short_term_area",
            "storage_items_density",
            "loan_items_density",
            "vip_items_density",
            "short_term_items_density",
            "storage_fee",
            "item_evaluation",
            "item_realization_markup",
            "average_item_value",
            "loan_interest_rate",
            "realization_share_storage",
            "realization_share_loan",
            "realization_share_vip",
            "realization_share_short_term",
            "rental_cost_per_m2",
            "total_area",
            "salary_expense",
            "miscellaneous_expenses",
            "depreciation_expense",
            "default_probability",
            "vip_extra_fee",
            "short_term_daily_rate"
        ]

        # Фильтрация параметров
        relevant_params = {k: v for k, v in params.items() if k in financials_required_keys}

        # Автоматический расчёт BEP при изменении параметров
        bep_result = calculate_bep(param_key, base_param_value, calculate_financials, **relevant_params)

        # Генерация диапазона параметров для графика
        if param_key == "storage_fee":
            param_values = np.linspace(params["storage_fee"] * 0.5, params["storage_fee"] * 1.5, 100)
        elif param_key == "loan_interest_rate":
            param_values = np.linspace(params["loan_interest_rate"] * 0.5, params["loan_interest_rate"] * 1.5, 100)
        elif param_key == "vip_extra_fee":
            param_values = np.linspace(500, 1500, 100)
        else:  # short_term_daily_rate
            param_values = np.linspace(params["short_term_daily_rate"] * 0.5, params["short_term_daily_rate"] * 1.5, 100)

        # Проверка наличия данных для построения графика
        try:
            profits = [
                calculate_financials(**{**relevant_params, param_key: val})["profit"]
                for val in param_values
            ]
        except KeyError as e:
            st.error(f"Ошибка при расчёте прибыли: {e}")
            profits = []

        # Если BEP не найден, расширяем диапазон и пытаемся снова
        if bep_result is None:
            st.warning("Начальный диапазон не содержит BEP. Попробуем расширить диапазон поиска.")
            # Расширяем диапазон на 50%
            param_values_extended = np.linspace(params[param_key] * 0.3, params[param_key] * 1.7, 200)
            try:
                profits_extended = [
                    calculate_financials(**{**relevant_params, param_key: val})["profit"]
                    for val in param_values_extended
                ]
                # Переопределяем BEP с расширенным диапазоном
                bep_result_extended = calculate_bep(param_key, base_param_value, calculate_financials, **relevant_params)
                if bep_result_extended is not None:
                    st.success(f"Точка безубыточности найдена в расширенном диапазоне: **{bep_result_extended:.2f}**")
                    # Отображаем график с расширенным диапазоном
                    display_bep(bep_result_extended, parameter_choice, param_values_extended, profits_extended)
                else:
                    st.error("Не удалось найти точку безубыточности даже после расширения диапазона.")
            except KeyError as e:
                st.error(f"Ошибка при расчёте прибыли в расширенном диапазоне: {e}")
        else:
            # Отображение BEP с первоначальным диапазоном
            display_bep(bep_result, parameter_choice, param_values, profits)

    with tab4:
        st.header("📋 Детализация")
        st.subheader("📦 Общее количество вещей")
        st.write(f"**Простое хранение:** {int(items['stored_items']):,}")
        st.write(f"**Хранение с займами:** {int(items['total_items_loan']):,}")
        st.write(f"**VIP-хранение:** {int(items['vip_stored_items']):,}")
        st.write(f"**Краткосрочное хранение:** {int(items['short_term_stored_items']):,}")

        st.subheader("📐 Площади для разных типов хранения (м²)")
        storage_data = {
            "Тип хранения": ["Простое хранение", "Хранение с займами", "VIP-хранение", "Краткосрочное хранение"],
            "Площадь (м²)": [
                params["storage_area"],
                params["loan_area"],
                params["vip_area"],
                params["short_term_area"]
            ],
            "Количество вещей": [
                items["stored_items"],
                items["total_items_loan"],
                items["vip_stored_items"],
                items["short_term_stored_items"]
            ],
        }
        df_storage = pd.DataFrame(storage_data)
        st.dataframe(df_storage.style.format({"Площадь (м²)": "{:,.2f}", "Количество вещей": "{:,.0f}"}))

        # Добавление Гистограммы Прибыли
        st.subheader("📊 Распределение Прибыли по Типам Хранения")
        profit_data = {
            "Тип хранения": ["Простое хранение", "Хранение с займами", "VIP-хранение", "Краткосрочное хранение"],
            "Прибыль (руб.)": [
                base_financials["storage_income"] - (params["storage_area"] * params["rental_cost_per_m2"]),
                base_financials["loan_income_after_realization"] - (params["loan_area"] * params["rental_cost_per_m2"]),
                base_financials["vip_income"] - (params["vip_area"] * params["rental_cost_per_m2"]),
                base_financials["short_term_income"] - (params["short_term_area"] * params["rental_cost_per_m2"])
            ]
        }
        df_profit = pd.DataFrame(profit_data)
        fig_hist = px.bar(df_profit, x="Тип хранения", y="Прибыль (руб.)",
                          title="Распределение Прибыли по Типам Хранения",
                          labels={"Прибыль (руб.)": "Прибыль (руб.)", "Тип хранения": "Тип хранения"},
                          text_auto=True)
        st.plotly_chart(fig_hist, use_container_width=True)

        st.subheader("📥 Скачать результаты")
        df_results = pd.DataFrame({
            "Показатель": [
                "Общий доход",
                "Общие расходы",
                "Прибыль",
                "Маржа прибыли (%)",
                "Рентабельность (%)",
                "Доход от реализации",
                ("Мин. сумма займа (учёт рисков и динамики) (руб.)" if not disable_extended and params["loan_interest_rate"] > 0 else "Мин. сумма займа (базовый расчёт) (руб.)")
            ],
            "Значение": [
                base_financials["total_income"],
                base_financials["total_expenses"],
                base_financials["profit"],
                profit_margin,
                profitability,
                base_financials["realization_income"],
                min_loan_amount
            ]
        })
        generate_download_link(df_results)

        if base_financials["loan_interest_rate"] == 0:
            st.warning("⚠️ Внимание: ставка по займам равна 0. Доход от займов будет отсутствовать.")

# Сохранение и загрузка сценариев после определения params
with st.sidebar.expander("💾 Сохранение/Загрузка сценариев"):
    save_scenario(params)
    loaded_params = load_scenario()
    if loaded_params:
        # Обновляем параметры только если загруженные данные корректны
        params_keys = params.keys()
        for key in loaded_params.keys():
            if key in params_keys:
                params[key] = loaded_params[key]
        # Обновляем доли хранения
        st.session_state.shares['storage_share'] = loaded_params.get('storage_share', 0.0)
        st.session_state.shares['loan_share'] = loaded_params.get('loan_share', 0.0)
        st.session_state.shares['vip_share'] = loaded_params.get('vip_share', 0.0)
        st.session_state.shares['short_term_share'] = loaded_params.get('short_term_share', 0.0)
        # Пересчитываем площади после загрузки сценария
        areas = calculate_areas(
            total_area=params["total_area"],
            useful_area_ratio=params["useful_area_ratio"],
            shelves_per_m2=params["shelves_per_m2"],
            storage_share=params["storage_share"],
            loan_share=params["loan_share"],
            vip_share=params["vip_share"],
            short_term_share=params["short_term_share"]
        )
        params.update(areas)

        # Перезапуск приложения для применения загруженных параметров
        # st.experimental_rerun()  # Удалено для предотвращения ошибки

# Информационное сообщение внизу страницы
st.info("""
### Как использовать приложение:
1. **Настройте параметры** в боковой панели слева.
2. В разделе **"📦 Параметры хранения"** выберите или введите дневной тариф для краткосрочного хранения.
3. Месячный доход краткосрочного хранения = дневной тариф × площадь × 30.
4. Перейдите на вкладку **"📊 Общие результаты"**, чтобы **просмотреть итоговые метрики**.
5. Используйте вкладку **"🔍 Точка безубыточности"** для **анализа точки безубыточности** выбранного параметра.
6. В разделе **"📈 Прогнозирование"** наблюдайте за **динамикой финансовых показателей** на выбранный горизонт.
7. **Скачивайте результаты** в формате CSV при необходимости.
8. **Сохраняйте и загружайте сценарии** для быстрого доступа к часто используемым настройкам.
""")
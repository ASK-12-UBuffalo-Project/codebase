from pathlib import Path
from jproperties import Properties

import pandas as pd
import hashlib
from shared import INPUTS
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shiny_validate import InputValidator, check

app_dir = Path(__file__).parent
configs = Properties()
properties = app_dir / "app.properties"
with open(properties, 'rb') as f:
    configs.load(f)
wordOne = configs.get("wordOne").data
wordTwo = configs.get("wordTwo").data
wordThree = configs.get("wordThree").data
passwordSet = configs.get("password").data

FORGETFULNESS_ITEMS = ["forgetToTake", "runOut", "inconvenient"]
BELIEF_ITEMS = ["feelConfident", "knowGoals", "haveSomeone", "workTogether"]
BEHAVIOR_ITEMS = [
    "takenMedicineMoreOften",
    "skippedMedicine",
    "skippedMedicineBecauseOfSideEffects",
    "skippedMedicineBecauseOfCost",
    "notHadMedicineWithYou",
]

WEIGHTS = {
    "forgetfulness": 1.5,
    "treatment_beliefs": 1.0,
    "behavior": 1.25,
}

# Mixed case handling: if the top two weighted domains are within this margin,
# treat the case as mixed rather than forcing a single dominant barrier.
MIXED_BARRIER_TOLERANCE = 0.20

# Keep these as constants so they are easy to adjust later if needed.
SIDE_EFFECT_TRIGGER_THRESHOLD = 3
COST_TRIGGER_THRESHOLD = 4

RECOMMENDATION_MAP = {
    "Forgetfulness": {
        "mild": "Offer a reminder strategy such as a phone alarm, habit cue, or simple daily reminder.",
        "moderate": (
            "Suggest digital reminders and refill support, such as SMS/app reminders, "
            "portal reminders, or pharmacy refill synchronization."
        ),
        "severe": (
            "Escalate to structured adherence support such as pharmacy synchronization, "
            "blister-pack support, and planned follow-up."
        ),
    },
    "Treatment beliefs": {
        "mild": "Provide brief education and clarify the purpose of the medication plan.",
        "moderate": (
            "Use brief counseling and teach-back to review goals, expected benefit, "
            "and the treatment plan."
        ),
        "severe": (
            "Recommend a more in-depth counseling discussion, pharmacist or educator involvement, "
            "and scheduled follow-up."
        ),
    },
    "Behavior": {
        "mild": (
            "Prompt the clinician to ask about the main reason for nonadherence, especially "
            "side effects, cost, or access."
        ),
        "moderate": (
            "Suggest medication review and targeted problem-solving around tolerability, "
            "affordability, or access barriers."
        ),
        "severe": (
            "Escalate to structured medication review, pharmacist involvement, and referral "
            "for cost-support or care-management follow-up when indicated."
        ),
    },
}

page1 = ui.navset_card_underline(
    ui.nav_panel(
        "Ask-12 Questionnaire",
        ui.include_css(app_dir / "styles.css"),
        ui.card(
            ui.card_header("Demographics"),
            INPUTS["id"],
            INPUTS["lname"],
            INPUTS["dob"],
        ),
        ui.card(
            ui.card_header("Inconvenience/Forgetfulness", class_="fs-4 bg-primary lead"),
            ui.h5("Lifestyles", class_="bg-primary-subtle lead"),
            INPUTS["forgetToTake"],
            INPUTS["runOut"],
            INPUTS["inconvenient"],
        ),
        ui.card(
            ui.card_header("Treatment Beliefs", class_="fs-4 bg-primary lead"),
            ui.h5("Attitudes & Beliefs", class_="bg-primary-subtle lead"),
            INPUTS["feelConfident"],
            INPUTS["knowGoals"],
            ui.h5("Help From Others", class_="bg-primary-subtle lead"),
            INPUTS["haveSomeone"],
            ui.h5("Talking with Healthcare Team", class_="bg-primary-subtle lead"),
            INPUTS["workTogether"],
        ),
        ui.card(
            ui.card_header("Behavior", class_="fs-4 bg-primary lead"),
            ui.h5("Taking Medicines", class_="bg-primary-subtle lead"),
            INPUTS["takenMedicineMoreOften"],
            INPUTS["skippedMedicine"],
            INPUTS["skippedMedicineBecauseOfSideEffects"],
            INPUTS["skippedMedicineBecauseOfCost"],
            INPUTS["notHadMedicineWithYou"],
        ),
        ui.div(
            ui.input_action_button("submit", "Submit", class_="btn btn-primary"),
            class_="d-flex justify-content-end",
        ),
    )   
)

page2 = ui.navset_card_underline(
    ui.nav_panel(
    "Subject Retrieval",
        ui.include_css(app_dir / "styles.css"),
        ui.card(
            ui.card_header("Demographics"),
            INPUTS["id"],
            INPUTS["lname"],
            INPUTS["dob"],
        ),
        ui.div(
            ui.input_password("password", "Password"),
            ui.input_action_button("login", "Login", class_="btn btn-primary"),
            class_="d-flex justify-content-end",
        ),
        ui.output_data_frame("patient_lookup"),
    )
)

def create_app_ui():
    return ui.page_navbar(
        ui.nav_spacer(),  # Push the navbar items to the right
        ui.nav_panel("Ask Questionnaire", page1),
        ui.nav_panel("Doctor Review", page2),
        title="Ask-12 Questionnaire Comprehensive Tool",
    )

def severity_from_avg(avg: float) -> str:
    if avg >= 3.5:
        return "severe"
    elif avg >= 2.5:
        return "moderate"
    return "mild"


def choose_barrier_pattern(weighted_domains: dict, tolerance: float = MIXED_BARRIER_TOLERANCE):
    ranked = sorted(weighted_domains.items(), key=lambda x: x[1], reverse=True)

    top_name, top_score = ranked[0]
    second_name, second_score = ranked[1]
    third_name, third_score = ranked[2]

    # If all three domains are close together, do not force a dominant barrier.
    if (top_score - third_score) <= tolerance:
        return "No Dominant Barrier", []

    # If the top two are close, treat as mixed.
    if (top_score - second_score) <= tolerance:
        return f"{top_name}, {second_name}", [top_name, second_name]

    return top_name, [top_name]


def combine_unique_texts(texts):
    seen = set()
    result = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            result.append(text)
    return " ".join(result)


def build_recommendation(primary_domains, domain_severities, risk, scored):
    if not primary_domains:
        recommendation = "No specific recommendation. Reassess barriers and monitor over time."
        severity_detail = "No dominant barrier"
    else:
        rec_texts = [
            RECOMMENDATION_MAP[domain][domain_severities[domain]]
            for domain in primary_domains
        ]
        recommendation = combine_unique_texts(rec_texts)
        severity_detail = "; ".join(
            [f"{domain}: {domain_severities[domain]}" for domain in primary_domains]
        )

    trigger_flags = []
    trigger_actions = []

    if scored["skippedMedicineBecauseOfSideEffects"] >= SIDE_EFFECT_TRIGGER_THRESHOLD:
        trigger_flags.append("Side-effect / tolerability concern")
        trigger_actions.append(
            "Review tolerability and discuss whether side effects are driving nonadherence."
        )

    if scored["skippedMedicineBecauseOfCost"] >= COST_TRIGGER_THRESHOLD:
        trigger_flags.append("Cost / affordability concern")
        trigger_actions.append(
            "Assess affordability and consider cost-support options, refill assistance, or lower-cost alternatives."
        )

    if trigger_actions:
        recommendation += " Additional flagged concern(s): " + " ".join(trigger_actions)

    if risk == "High":
        recommendation += " Closer follow-up may also be appropriate."

    return recommendation, trigger_flags, severity_detail


def calculate_scores(values):
    scored = {
        key: int(values[key])
        for key in FORGETFULNESS_ITEMS + BELIEF_ITEMS + BEHAVIOR_ITEMS
    }

    forgetfulness_sum = sum(scored[q] for q in FORGETFULNESS_ITEMS)
    beliefs_sum = sum(scored[q] for q in BELIEF_ITEMS)
    behavior_sum = sum(scored[q] for q in BEHAVIOR_ITEMS)

    forgetfulness_avg = forgetfulness_sum / len(FORGETFULNESS_ITEMS)
    beliefs_avg = beliefs_sum / len(BELIEF_ITEMS)
    behavior_avg = behavior_sum / len(BEHAVIOR_ITEMS)

    weighted_forgetfulness = forgetfulness_avg * WEIGHTS["forgetfulness"]
    weighted_behavior = behavior_avg * WEIGHTS["behavior"]
    weighted_beliefs = beliefs_avg * WEIGHTS["treatment_beliefs"]

    weighted_domains = {
        "Behavior": weighted_behavior,
        "Treatment beliefs": weighted_beliefs,
        "Forgetfulness": weighted_forgetfulness,
    }

    dominant_barrier, primary_domains = choose_barrier_pattern(weighted_domains)

    total_score = forgetfulness_sum + beliefs_sum + behavior_sum

    if total_score >= 41:
        risk = "High"
    elif total_score >= 21:
        risk = "Medium"
    else:
        risk = "Low"

    domain_severities = {
        "Forgetfulness": severity_from_avg(forgetfulness_avg),
        "Treatment beliefs": severity_from_avg(beliefs_avg),
        "Behavior": severity_from_avg(behavior_avg),
    }

    if not primary_domains:
        domain_severity = "none"
    elif len(primary_domains) == 1:
        domain_severity = domain_severities[primary_domains[0]]
    else:
        domain_severity = "mixed"

    recommendation, trigger_flags, domain_severity_detail = build_recommendation(
        primary_domains,
        domain_severities,
        risk,
        scored,
    )

    if dominant_barrier == "Forgetfulness":
        final_sentence = (
            f"Responses suggest a {domain_severity} forgetfulness-related adherence barrier."
        )
    elif dominant_barrier == "Treatment beliefs":
        final_sentence = (
            f"Responses suggest a {domain_severity} treatment-belief barrier that may be affecting adherence."
        )
    elif dominant_barrier == "Behavior":
        final_sentence = (
            f"Responses suggest a {domain_severity} behavior-related adherence barrier."
        )
    elif dominant_barrier == "No Dominant Barrier":
        final_sentence = "Responses do not suggest a single dominant barrier at this time."
    else:
        domain_phrase = " and ".join([d.lower() for d in primary_domains])
        final_sentence = (
            f"Responses suggest a mixed {domain_phrase} barrier pattern "
            f"({domain_severity_detail})."
        )

    if risk == "High":
        final_sentence += " Overall risk is high."

    if trigger_flags:
        final_sentence += " Additional flagged concern(s): " + ", ".join(trigger_flags) + "."

    return {
        "forgetfulness_sum": forgetfulness_sum,
        "beliefs_sum": beliefs_sum,
        "behavior_sum": behavior_sum,
        "forgetfulness_avg": round(forgetfulness_avg, 2),
        "beliefs_avg": round(beliefs_avg, 2),
        "behavior_avg": round(behavior_avg, 2),
        "weighted_forgetfulness": round(weighted_forgetfulness, 2),
        "weighted_behavior": round(weighted_behavior, 2),
        "weighted_beliefs": round(weighted_beliefs, 2),
        "total_score": total_score,
        "risk": risk,
        "dominant_barrier": dominant_barrier,
        "domain_severity": domain_severity,
        "domain_severity_detail": domain_severity_detail,
        "trigger_flags": "; ".join(trigger_flags) if trigger_flags else "",
        "recommendation": recommendation,
        "final_sentence": final_sentence,
    }


def server(input: Inputs, output: Outputs, session: Session):
    input_validator = InputValidator()

    input_validator.add_rule("forgetToTake", check.required())
    input_validator.add_rule("runOut", check.required())
    input_validator.add_rule("inconvenient", check.required())
    input_validator.add_rule("feelConfident", check.required())
    input_validator.add_rule("knowGoals", check.required())
    input_validator.add_rule("haveSomeone", check.required())
    input_validator.add_rule("workTogether", check.required())
    input_validator.add_rule("takenMedicineMoreOften", check.required())
    input_validator.add_rule("skippedMedicine", check.required())
    input_validator.add_rule("skippedMedicineBecauseOfSideEffects", check.required())
    input_validator.add_rule("skippedMedicineBecauseOfCost", check.required())
    input_validator.add_rule("notHadMedicineWithYou", check.required())

    @reactive.effect
    @reactive.event(input.login)
    def login():
        password = input.password()
        if password != passwordSet:
            ui.modal_show(
                ui.modal(
                    "Incorrect password. Please try again.",
                    title="Login Failed",
                    easy_close=True,
                )
            )
        else:
            df = pd.read_csv(app_dir / "responses.csv")

            @render.data_frame
            def patient_lookup():
                #print(input.id(), input.lname(), input.dob())
                if(wordOne == "id"):
                    words = [(str(input.id()))]
                elif(wordOne == "lname"):
                    words = [str(input.lname())]
                elif(wordOne == "dob"):
                    words = [str(input.dob())]
                if wordTwo == "id":
                    words.append(str(input.id()))
                elif wordTwo == "lname":
                    words.append(str(input.lname()))
                elif wordTwo == "dob":
                    words.append(str(input.dob()))
                if wordThree == "id":
                    words.append(str(input.id()))
                elif wordThree == "lname":
                    words.append(str(input.lname()))
                elif wordThree == "dob":
                    words.append(str(input.dob()))
                hashed_id = hashlib.sha256("".join(words).encode()).hexdigest()

                df2 = df[
                    [
                        "id",
                        "dominant_barrier",
                        "domain_severity",
                        "domain_severity_detail",
                        "risk",
                        "trigger_flags",
                        "recommendation",
                        "final_sentence",
                    ]
                ]

                df_filtered = df2[df2["id"] == hashed_id]
                df_output = df_filtered.drop(columns=["id"])
                return df_output

    @reactive.effect
    @reactive.event(input.submit)
    def save_to_csv():
        input_validator.enable()
        if not input_validator.is_valid():
            return

        values = {k: input[k]() for k in INPUTS.keys()}

        values[wordOne] = hashlib.sha256(
            (values[wordOne] + values[wordTwo] + str(values[wordThree])).encode()
        ).hexdigest()
        values.pop(wordThree)
        values.pop(wordTwo)

        score_results = calculate_scores(values)

        row = {**values, **score_results}
        df = pd.DataFrame([row])

        responses = app_dir / "responses.csv"
        if not responses.exists():
            df.to_csv(responses, mode="a", header=True, index=False)
        else:
            df.to_csv(responses, mode="a", header=False, index=False)

        ui.modal_show(
            ui.modal(
                "Form submitted successfully. Thank you!",
                title="Submission complete",
                easy_close=True,
            )
        )


app = App(create_app_ui(), server)
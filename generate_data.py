"""
generate_data.py  –  Smart Classroom (Upgraded)
Generates rich student-topic datasets with:
  - prerequisite scores & days since learning them
  - attempt patterns, time per attempt, score variance
  - hint usage, video rewatches, help-seeking behaviour
  - struggle_reason  (WHY they struggle)
  - recommended_action  (WHAT to do)
"""

import pandas as pd
import numpy as np
import random
import os

random.seed(42)
np.random.seed(42)

subjects = {
    "Maths":          ["Arithmetic", "Algebra", "Geometry", "Trigonometry", "Statistics", "Probability"],
    "Science":        ["Physics", "Chemistry", "Biology", "Environmental Science", "Space Science"],
    "Social Science": ["History", "Geography", "Civics", "Economics", "Political Science"],
}

def get_prerequisite(subject, topic):
    topics = subjects[subject]
    idx = topics.index(topic)
    return topics[idx - 1] if idx > 0 else None

def derive_struggle_reason(row):
    if row["score"] >= 70:
        return "none"
    if row["prerequisite_score"] < 55:
        return "prerequisite_gap"
    if row["avg_time_per_attempt"] < 12 and row["score"] < 55:
        return "guessing"
    if row["hint_usage_count"] >= 5 and row["score"] < 60:
        return "conceptual_misunderstanding"
    if row["score_variance"] > 22 and row["session_count"] >= 3:
        return "unstable_understanding"
    if row["avg_time_per_attempt"] > 90 and row["score"] < 60:
        return "cognitive_overload"
    if row["days_since_prerequisite"] > 45 and row["prerequisite_score"] >= 55:
        return "forgetting"
    if row["num_attempts"] <= 2 and row["score"] < 60:
        return "low_engagement"
    return "conceptual_misunderstanding"

ACTION_MAP = {
    "none":                        "maintain_current_pace",
    "prerequisite_gap":            "revisit_prerequisite_topic",
    "guessing":                    "enforce_reflection_before_submit",
    "conceptual_misunderstanding": "assign_worked_examples",
    "unstable_understanding":      "spaced_repetition_practice",
    "cognitive_overload":          "break_topic_into_subtasks",
    "forgetting":                  "schedule_revision_session",
    "low_engagement":              "increase_interactive_activities",
}

def attempt_pattern_label(scores_list):
    if len(scores_list) < 2:
        return "insufficient_data"
    diffs = [scores_list[i+1] - scores_list[i] for i in range(len(scores_list)-1)]
    avg_diff = sum(diffs) / len(diffs)
    if avg_diff > 3:   return "improving"
    if avg_diff < -3:  return "declining"
    if float(np.var(scores_list)) > 200: return "volatile"
    return "stuck"

def make_row(student_id, school_id, grade, subject, topic):
    prereq       = get_prerequisite(subject, topic)
    prereq_score = round(max(0, min(100, random.gauss(62, 18))), 1) if prereq else 100.0
    days_since   = random.randint(1, 90) if prereq else 0

    num_attempts     = random.randint(1, 8)
    per_attempt_time = round(max(5, random.gauss(35, 25)), 1)
    time_on_task     = round(per_attempt_time * num_attempts, 1)

    base_score       = prereq_score * 0.55 + random.gauss(25, 15)
    score            = round(max(0, min(100, base_score)), 1)

    attempt_scores   = [max(0, min(100, score + random.gauss(0, 8))) for _ in range(num_attempts)]
    score_var        = round(float(np.var(attempt_scores)), 2)

    hint_usage       = random.randint(0, 8)
    video_rewatch    = random.randint(0, 5)
    help_seeking     = 1 if (score < 55 and random.random() > 0.4) else 0
    session_count    = random.randint(1, 6)
    att_pattern      = attempt_pattern_label(attempt_scores)
    difficulty_score = round(1 - score / 100, 4)

    row = {
        "student_id":               f"S_{school_id}_{student_id:03d}",
        "school_id":                school_id,
        "class":                    grade,
        "subject":                  subject,
        "topic":                    topic,
        "prerequisite_topic":       prereq if prereq else "none",
        "prerequisite_score":       prereq_score,
        "days_since_prerequisite":  days_since,
        "num_attempts":             num_attempts,
        "avg_time_per_attempt":     per_attempt_time,
        "time_on_task":             time_on_task,
        "score":                    score,
        "score_variance":           score_var,
        "hint_usage_count":         hint_usage,
        "video_rewatch_count":      video_rewatch,
        "help_seeking_behavior":    help_seeking,
        "session_count":            session_count,
        "attempt_pattern":          att_pattern,
        "difficulty_score":         difficulty_score,
    }
    row["struggle_reason"]    = derive_struggle_reason(row)
    row["recommended_action"] = ACTION_MAP[row["struggle_reason"]]
    return row

def create_school_data(filepath, school_id, n_students=12):
    rows = []
    sid  = 1
    for grade in range(5, 11):
        for subject, topics in subjects.items():
            for topic in topics:
                for _ in range(n_students):
                    rows.append(make_row(sid, school_id, grade, subject, topic))
                    sid += 1
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False)
    print(f"[DataGen] {filepath}: {len(df)} rows generated.")
    return df

if __name__ == "__main__":
    create_school_data("clients/school_1/data1.csv", "A", n_students=12)
    create_school_data("clients/school_2/data2.csv", "B", n_students=8)
    print("\nDatasets ready with struggle_reason + recommended_action columns.")

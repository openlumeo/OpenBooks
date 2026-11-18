"""Label sets of the typed heads. No torch import here, so anything that needs only the names stays light."""
ROLES = ["other", "date", "desc", "debit", "credit", "balance"]
VTYPES = ["text", "date", "money", "code"]

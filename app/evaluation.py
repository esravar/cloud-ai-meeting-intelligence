import uuid

from app.embeddings import EmbeddingProvider
from app.repository import MeetingRepository
from app.schemas import EvaluationCase, EvaluationResponse


class RetrievalEvaluationService:
    def __init__(
        self,
        repository: MeetingRepository,
        embeddings: EmbeddingProvider,
    ):
        self._repository = repository
        self._embeddings = embeddings

    def evaluate(
        self,
        owner_id: uuid.UUID,
        cases: list[EvaluationCase],
        top_k: int,
    ) -> EvaluationResponse:
        hits = 0
        reciprocal_rank_sum = 0.0
        for case in cases:
            chunks = self._repository.search(
                owner_id,
                self._embeddings.embed_query(case.question),
                self._embeddings.model_name,
                self._embeddings.dimensions,
                top_k,
            )
            ranked_meetings = list(dict.fromkeys(c.meeting_id for c in chunks))
            if case.expected_meeting_id in ranked_meetings:
                rank = ranked_meetings.index(case.expected_meeting_id) + 1
                hits += 1
                reciprocal_rank_sum += 1.0 / rank
        count = len(cases)
        return EvaluationResponse(
            case_count=count,
            hit_rate_at_k=round(hits / count, 4),
            mean_reciprocal_rank=round(reciprocal_rank_sum / count, 4),
        )

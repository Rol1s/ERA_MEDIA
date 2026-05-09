from dataclasses import dataclass


@dataclass(frozen=True)
class PublishResult:
    status: str
    external_message_id: str | None = None
    error_message: str | None = None


class MaxPublisherAdapter:
    def publish(self, channel_slug: str, title: str, body: str) -> PublishResult:
        raise NotImplementedError


class StubMaxPublisherAdapter(MaxPublisherAdapter):
    def publish(self, channel_slug: str, title: str, body: str) -> PublishResult:
        return PublishResult(
            status="waiting_human",
            error_message="MAX API is not connected yet. Manual copy is required.",
        )


from __future__ import annotations

from .models import ContextRequest, ContextSource, ResolvedContextBundle, ResolvedContextEntry


class LocalFirstContextResolver:
    ORDER = (
        ContextSource.JIRA,
        ContextSource.REPOSITORY,
        ContextSource.RUN_STATE,
        ContextSource.INTERNAL_KNOWLEDGE,
        ContextSource.FIRST_PARTY,
        ContextSource.EXTERNAL_RESEARCH,
    )

    def resolve(self, request: ContextRequest) -> ResolvedContextBundle:
        entries: list[ResolvedContextEntry] = []

        for source in self.ORDER:
            for index, content in enumerate(request.available_context.get(source, []), start=1):
                entries.append(
                    ResolvedContextEntry(
                        source=source,
                        content=content,
                        provenance=f"{source.value}:{index}",
                    )
                )

        uses_external_research = any(
            entry.source == ContextSource.EXTERNAL_RESEARCH for entry in entries
        )
        if uses_external_research and not request.external_research_reason:
            raise ValueError(
                "External research requires an insufficiency reason from earlier context stages."
            )

        return ResolvedContextBundle(
            entries=entries,
            external_research_reason=request.external_research_reason,
        )

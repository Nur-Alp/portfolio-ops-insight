import { Construction } from "lucide-react";
import { EmptyState } from "../components/ui/AsyncState";
import { Panel } from "../components/ui/Panel";
import { PageFrame } from "../components/ui/PageFrame";

export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <PageFrame title={title} eyebrow="OSIP / Контролируемый MVP" description={description}>
      <Panel title="Страница подготовлена" subtitle="Оболочка, фильтры, состояния и контролируемый API уже доступны.">
        <EmptyState
          title={`Реализация раздела «${title}» — следующий этап`}
          detail="Страница намеренно не показывает неподтверждённые или искусственно рассчитанные показатели портфеля."
          action={<Construction aria-hidden="true" />}
        />
      </Panel>
    </PageFrame>
  );
}

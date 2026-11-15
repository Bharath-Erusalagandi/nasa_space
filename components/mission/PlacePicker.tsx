"use client";

import { useMemo } from "react";
import { RiSearchLine } from "@remixicon/react";
import { ComboBox, ComboBoxItem, ComboBoxSection } from "@/components/base/combobox/combobox";
import { useMission } from "@/lib/mission/state";
import type { Place, PlaceKind } from "@/lib/trends/types";

const GROUPS: { kind: PlaceKind; title: string }[] = [
  { kind: "town", title: "Towns" },
  { kind: "facility", title: "Facilities" },
  { kind: "cell", title: "Grid cells" },
];

const byName = (a: Place, b: Place) => a.name.localeCompare(b.name);

export function PlacePicker() {
  const places = useMission((s) => s.index?.places);
  const placeId = useMission((s) => s.placeId);
  const selectPlace = useMission((s) => s.selectPlace);

  const groups = useMemo(
    () =>
      GROUPS.map((g) => ({ ...g, places: (places ?? []).filter((p) => p.kind === g.kind).sort(byName) })).filter(
        (g) => g.places.length,
      ),
    [places],
  );

  return (
    <ComboBox
      aria-label="Place"
      placeholder={places ? "Search places" : "Loading places"}
      leadingIcon={RiSearchLine}
      isDisabled={!places}
      selectedKey={placeId}
      onSelectionChange={(key) => key !== null && selectPlace(String(key))}
      menuTrigger="focus"
      emptyMessage="No place with that name"
      className="w-72"
      popoverClassName="min-w-80"
    >
      {groups.map((g) => (
        <ComboBoxSection key={g.kind} id={g.kind} title={g.title}>
          {g.places.map((p) => (
            <ComboBoxItem key={p.id} id={p.id} textValue={p.name}>
              <span className="truncate">{p.name}</span>
              {p.type ? <span className="shrink-0 text-body-2-regular text-text-tertiary">{p.type}</span> : null}
            </ComboBoxItem>
          ))}
        </ComboBoxSection>
      ))}
    </ComboBox>
  );
}

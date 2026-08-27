"use client";

import EwsSubjectRiskDrilldownCard from "@/components/dashboard/EwsSubjectRiskDrilldownCard";

interface EwsSubjectRiskTabProps {
    modelVersion: string;
    refreshKey: number;
    schoolYearId: number;
    semesterIndex: number;
    week: number;
}

export default function EwsSubjectRiskTab({
    modelVersion,
    refreshKey,
    schoolYearId,
    semesterIndex,
    week,
}: EwsSubjectRiskTabProps) {
    return (
        <div className="space-y-6">
            <EwsSubjectRiskDrilldownCard
                key={`${schoolYearId}-${semesterIndex}-${week}-${modelVersion}-${refreshKey}`}
                schoolYearId={schoolYearId}
                semesterIndex={semesterIndex}
                week={week}
                modelVersion={modelVersion}
            />
        </div>
    );
}
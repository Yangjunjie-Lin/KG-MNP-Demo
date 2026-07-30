// Mapping / alignment records stored in Neo4j

MATCH (map:MappingRecord)
RETURN map.id AS term,
       'MAPPING' AS alignmentStatus,
       map.sourceApi AS mapApi,
       map.sourceFieldPath AS mapField,
       map.targetTerm AS mapTarget,
       map.mappingReviewStatus AS mapReview,
       map.mappingType AS mappingType
ORDER BY mapApi, mapTarget

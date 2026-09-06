from __future__ import annotations

from rdflib import OWL, RDF, RDFS, Literal
from rdflib.namespace import SH

LEVEL=["NO_CHANGE","ANNOTATION_ONLY","PATCH_COMPATIBLE","RELAXING","DATA_CHANGE","ADDITIVE","POTENTIALLY_BREAKING","BREAKING","UNKNOWN_REQUIRES_REVIEW"]
ANNOT={RDFS.label,RDFS.comment}
def worst(values): return max(values,key=lambda x:LEVEL.index(x),default="NO_CHANGE")
def _bound(p,o,n):
    try: old=int(o) if o is not None else None; new=int(n) if n is not None else None
    except (ValueError,TypeError): return "UNKNOWN_REQUIRES_REVIEW","INVALID_CARDINALITY"
    if p in {OWL.minCardinality,OWL.minQualifiedCardinality,SH.minCount,SH.minLength}: return ("BREAKING" if new is not None and (old is None or new>old) else "RELAXING"),"CARDINALITY_BOUND_CHANGED"
    if p in {OWL.maxCardinality,OWL.maxQualifiedCardinality,SH.maxCount,SH.maxLength}: return ("BREAKING" if new is not None and (old is None or new<old) else "RELAXING"),"CARDINALITY_BOUND_CHANGED"
    return "BREAKING","EXACT_CARDINALITY_CHANGED"
def classify_tbox(s,p,o,n,*_):
    if p in ANNOT: return ("ANNOTATION_ONLY" if o is None or n is None else "POTENTIALLY_BREAKING"),"PUBLIC_LABEL_OR_DEFINITION_CHANGED"
    if p==RDF.type:
        if o in {OWL.Class,OWL.ObjectProperty,OWL.DatatypeProperty} and n is None:return "BREAKING","PUBLIC_TERM_REMOVED"
        if n in {OWL.Class,OWL.ObjectProperty,OWL.DatatypeProperty} and o is None:return "ADDITIVE","PUBLIC_TERM_ADDED"
        if o in {OWL.Class,OWL.ObjectProperty,OWL.DatatypeProperty} and n in {OWL.Class,OWL.ObjectProperty,OWL.DatatypeProperty} and o!=n:return "BREAKING","PUBLIC_TERM_RETYPED"
        if n in {OWL.FunctionalProperty,OWL.InverseFunctionalProperty,OWL.IrreflexiveProperty,OWL.AsymmetricProperty}:return "BREAKING","RESTRICTIVE_CHARACTERISTIC_ADDED"
    if p in {RDFS.subClassOf,RDFS.subPropertyOf}: return ("POTENTIALLY_BREAKING" if o is None else "BREAKING"),"HIERARCHY_CHANGED"
    if p in {OWL.disjointWith,OWL.propertyDisjointWith}: return ("BREAKING" if n is not None else "RELAXING"),"DISJOINTNESS_CHANGED"
    if p in {RDFS.domain,RDFS.range}: return ("BREAKING" if o is not None else "POTENTIALLY_BREAKING"),"DOMAIN_RANGE_CHANGED"
    if p in {OWL.minCardinality,OWL.maxCardinality,OWL.qualifiedCardinality,SH.minCount,SH.maxCount,SH.minLength,SH.maxLength}: return _bound(p,o,n)
    if p==OWL.imports:return "BREAKING","BASELINE_IMPORT_CHANGED"
    return "UNKNOWN_REQUIRES_REVIEW","UNSUPPORTED_OWL_CONSTRUCT"
def classify_abox(s,p,o,n,*_):
    if p in {OWL.sameAs,OWL.differentFrom}:return "BREAKING","IDENTITY_ASSERTION_CHANGED"
    if p==RDF.type:return ("DATA_CHANGE" if o is None else "POTENTIALLY_BREAKING"),"CLASS_ASSERTION_CHANGED"
    if isinstance(o,Literal) or isinstance(n,Literal):return "DATA_CHANGE","LITERAL_VALUE_CHANGED"
    return ("DATA_CHANGE" if o is None else "POTENTIALLY_BREAKING"),"ASSERTION_CHANGED"
def classify_shacl(s,p,o,n,*_):
    if p==SH.message:return "ANNOTATION_ONLY","SHACL_MESSAGE_CHANGED"
    if p in {SH.minCount,SH.maxCount,SH.minLength,SH.maxLength}:return _bound(p,o,n)
    if p in {SH.datatype,SH.nodeKind,SH.pattern,SH["class"],SH["in"]}:return ("RELAXING" if n is None else "BREAKING"),"SHACL_CONSTRAINT_CHANGED"
    if p in {RDF.type,SH.targetClass,SH.targetNode,SH.path,SH.property}:return ("POTENTIALLY_BREAKING" if n is None else "BREAKING"),"SHAPE_COVERAGE_CHANGED"
    return "UNKNOWN_REQUIRES_REVIEW","UNSUPPORTED_SHACL_CONSTRUCT"

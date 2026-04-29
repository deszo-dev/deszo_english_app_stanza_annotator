From Stdlib Require Import Arith.Arith.
From Stdlib Require Import Lists.List.
From Stdlib Require Import micromega.Lia.
From Stdlib Require Import Strings.String.

Import ListNotations.
Open Scope string_scope.
Open Scope list_scope.
Open Scope nat_scope.

Module StanzaAnnotatorSpec.

Inductive Processor : Type :=
| Tokenize
| Mwt
| Pos
| LemmaProc
| Depparse
| Ner.

Definition default_processors : list Processor :=
  [Tokenize; Mwt; Pos; LemmaProc; Depparse; Ner].

Inductive LogLevel : Type :=
| LogDebug
| LogInfo
| LogWarning
| LogError.

Inductive ExitCode : Type :=
| Success
| ExpectedError
| SystemError.

Definition exit_code_value (c : ExitCode) : nat :=
  match c with
  | Success => 0
  | ExpectedError => 1
  | SystemError => 2
  end.

Theorem exit_code_contract :
  exit_code_value Success = 0 /\
  exit_code_value ExpectedError = 1 /\
  exit_code_value SystemError >= 2.
Proof.
  repeat split; simpl; lia.
Qed.

Record AnnotatorConfig : Type := {
  cfg_language : string;
  cfg_use_gpu : bool;
  cfg_processors : list Processor;
  cfg_tokenize_pretokenized : bool;
  cfg_auto_download : bool;
  cfg_debug : bool
}.

Definition valid_config (c : AnnotatorConfig) : Prop :=
  cfg_language c = "en" /\ cfg_processors c = default_processors.

Record PreparedInput : Type := {
  input_text : string;
  input_valid_utf8 : Prop;
  input_preprocessed : Prop
}.

Definition non_empty_string (s : string) : Prop := s <> "".
Definition valid_span (start finish : nat) : Prop := start <= finish.

Record Word : Type := {
  word_surface : string;
  word_lemma : string;
  word_upos : string;
  word_xpos : option string;
  word_feats : option string;
  word_head : nat;
  word_deprel : string;
  word_start_char : nat;
  word_end_char : nat
}.

Definition valid_word (w : Word) : Prop :=
  valid_span (word_start_char w) (word_end_char w) /\
  non_empty_string (word_surface w) /\
  non_empty_string (word_upos w) /\
  non_empty_string (word_deprel w).

Record Token : Type := {
  token_surface : string;
  token_words : list Word
}.

Definition valid_token (t : Token) : Prop :=
  non_empty_string (token_surface t) /\
  token_words t <> [] /\
  Forall valid_word (token_words t).

Record Sentence : Type := {
  sentence_surface : string;
  sentence_tokens : list Token;
  sentence_words : list Word
}.

Definition valid_sentence (s : Sentence) : Prop :=
  Forall valid_token (sentence_tokens s) /\
  Forall valid_word (sentence_words s).

Record Entity : Type := {
  entity_surface : string;
  entity_type : string;
  entity_start_char : nat;
  entity_end_char : nat
}.

Definition valid_entity (e : Entity) : Prop :=
  non_empty_string (entity_surface e) /\
  non_empty_string (entity_type e) /\
  valid_span (entity_start_char e) (entity_end_char e).

Record AnnotatedDocument : Type := {
  doc_sentences : list Sentence;
  doc_entities : list Entity
}.

Definition valid_document (d : AnnotatedDocument) : Prop :=
  Forall valid_sentence (doc_sentences d) /\
  Forall valid_entity (doc_entities d).

Parameter RawStanzaDocument : Type.
Parameter project_stanza_document : RawStanzaDocument -> AnnotatedDocument.
Parameter project_stanza_document_preserves_schema :
  forall raw : RawStanzaDocument,
    valid_document (project_stanza_document raw).

Definition annotate_core
  (_input : PreparedInput)
  (_config : AnnotatorConfig)
  (raw : RawStanzaDocument) : AnnotatedDocument :=
  project_stanza_document raw.

Theorem annotate_core_deterministic :
  forall input config raw,
    annotate_core input config raw = annotate_core input config raw.
Proof.
  reflexivity.
Qed.

Theorem annotate_core_preserves_schema :
  forall input config raw,
    valid_document (annotate_core input config raw).
Proof.
  intros input config raw.
  unfold annotate_core.
  apply project_stanza_document_preserves_schema.
Qed.

Definition DebugTrace : Type := list string.

Definition observe_debug
  (doc : AnnotatedDocument)
  (_trace : DebugTrace) : AnnotatedDocument :=
  doc.

Theorem debug_does_not_change_result :
  forall doc trace,
    observe_debug doc trace = doc.
Proof.
  reflexivity.
Qed.

Inductive CliStatus : Type :=
| CliOk (doc : AnnotatedDocument)
| CliExpectedDataError
| CliSystemFailure.

Definition cli_exit_code (r : CliStatus) : ExitCode :=
  match r with
  | CliOk _ => Success
  | CliExpectedDataError => ExpectedError
  | CliSystemFailure => SystemError
  end.

Theorem cli_exit_code_mapping :
  forall d,
    cli_exit_code (CliOk d) = Success /\
    cli_exit_code CliExpectedDataError = ExpectedError /\
    cli_exit_code CliSystemFailure = SystemError.
Proof.
  intro d.
  repeat split; reflexivity.
Qed.

Record CliObservation : Type := {
  obs_stdout : option AnnotatedDocument;
  obs_stderr : list string;
  obs_exit : ExitCode
}.

Definition valid_cli_observation (o : CliObservation) : Prop :=
  match obs_exit o with
  | Success => exists d, obs_stdout o = Some d
  | ExpectedError => obs_stdout o = None
  | SystemError => obs_stdout o = None
  end.

Theorem non_success_has_no_stdout_payload :
  forall o,
    valid_cli_observation o ->
    obs_exit o <> Success ->
    obs_stdout o = None.
Proof.
  intros o Hvalid Hnot_success.
  destruct o as [out err exit].
  simpl in *.
  destruct exit; try contradiction; exact Hvalid.
Qed.

End StanzaAnnotatorSpec.

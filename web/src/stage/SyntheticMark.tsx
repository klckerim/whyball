import styles from "./stage.module.css";

/** Always on the stage and the overlay (UI_SPEC T8): the match, teams and players are generated. */
export function SyntheticMark() {
  return (
    <div className={styles.synthetic} title="Generated, seeded match data; no real club, player or match">
      SYNTHETIC DATA
    </div>
  );
}

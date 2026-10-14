import * as Dialog from "@radix-ui/react-dialog";

import styles from "./app.module.css";
import { SHORTCUTS } from "./keys";

export function HelpDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.dialog}>
          <Dialog.Title className={styles.dialogTitle}>Keyboard shortcuts</Dialog.Title>
          <Dialog.Description className={styles.detail}>They do nothing while you type in a field.</Dialog.Description>
          <dl className={styles.keys}>
            {SHORTCUTS.map((s) => (
              <div key={s.keys}>
                <dt>
                  <kbd>{s.keys}</kbd>
                </dt>
                <dd>{s.action}</dd>
              </div>
            ))}
          </dl>
          <Dialog.Close className={styles.textButton}>Close</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

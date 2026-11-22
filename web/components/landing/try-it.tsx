// "See it prove a file, live." Server component. The demo itself is a client island inside a static device frame.
import { DeviceFrame } from "./device-frame";
import { LiveDemo } from "./live-demo";
import styles from "./try-it.module.css";

export function TryIt() {
  return (
    <section id="try-it" aria-labelledby="try-it-heading" className={styles.section}>
      <div className={styles.container}>
        <header className={styles.intro}>
          <h2 id="try-it-heading" className={`t-display t-h2 ${styles.heading}`}>
            See it prove a file, live.
          </h2>
          <p className={`t-lede ${styles.lede}`}>
            Choose a file and run it through the same engine the workspace uses. The proof appears as it is computed.
          </p>
        </header>
        <div className={styles.frame}>
          <DeviceFrame label="Open Books workspace">
            <LiveDemo autoplay />
          </DeviceFrame>
        </div>
      </div>
    </section>
  );
}

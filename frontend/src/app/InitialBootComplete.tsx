import { useEffect } from "react";
import { completeInitialBoot } from "./initial-boot";

export function InitialBootComplete() {
  useEffect(() => {
    completeInitialBoot(document.getElementById("root"), document.getElementById("boot-loader"));
  }, []);

  return null;
}

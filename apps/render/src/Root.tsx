import React from "react";
import { Composition } from "remotion";
import { ReelsBasic } from "./compositions/ReelsBasic";
import { ReelsParallax } from "./compositions/ReelsParallax";
import {
  CATALOG_SEGMENT,
  StyleCatalog,
  calculateCatalogMetadata,
  catalogDefaultProps,
  styleCatalogSchema,
} from "./compositions/StyleCatalog";
import { defaultProps, reelsPropsSchema } from "./props";
import { calculateReelsMetadata } from "./lib/metadata";
import { FPS, HEIGHT, WIDTH, totalFrames } from "./lib/timing";
import type { CompositionId } from "./lib/compositions";

export const RemotionRoot: React.FC = () => {
  const common = {
    width: WIDTH,
    height: HEIGHT,
    fps: FPS,
    durationInFrames: totalFrames(defaultProps.scenes),
    schema: reelsPropsSchema,
    defaultProps,
    calculateMetadata: calculateReelsMetadata,
  };
  return (
    <>
      <Composition id={"ReelsBasic" satisfies CompositionId} component={ReelsBasic} {...common} />
      <Composition id={"ReelsParallax" satisfies CompositionId} component={ReelsParallax} {...common} />
      {/* Review-only (not a render-job target): every StyleTheme × 2 text presets. */}
      <Composition
        id="StyleCatalog"
        component={StyleCatalog}
        width={WIDTH}
        height={HEIGHT}
        fps={FPS}
        durationInFrames={catalogDefaultProps.themes.length * CATALOG_SEGMENT}
        schema={styleCatalogSchema}
        defaultProps={catalogDefaultProps}
        calculateMetadata={calculateCatalogMetadata}
      />
    </>
  );
};

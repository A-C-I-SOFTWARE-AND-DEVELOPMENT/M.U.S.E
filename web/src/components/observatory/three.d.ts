/**
 * Minimal ambient type declarations for `three` (0.180.0).
 *
 * three ships no bundled .d.ts and @types/three is not installed in this
 * workspace (no new deps allowed). This file declares ONLY the API surface
 * used by the Observatory ambient layer, so `import * as THREE from "three"`
 * stays fully type-checked under `strict` + `noImplicitAny`.
 *
 * INTEGRATOR NOTE: if @types/three is ever added to the project, DELETE this
 * file — an ambient `declare module "three"` would conflict with the real
 * type package.
 */
declare module "three" {
  export const AdditiveBlending: number;

  export class Color {
    constructor(color?: number | string);
    r: number;
    g: number;
    b: number;
    setHSL(h: number, s: number, l: number): this;
    offsetHSL(h: number, s: number, l: number): this;
    copy(color: Color): this;
  }

  export class Vector3 {
    x: number;
    y: number;
    z: number;
    set(x: number, y: number, z: number): this;
  }

  export class Euler {
    x: number;
    y: number;
    z: number;
    set(x: number, y: number, z: number): this;
  }

  export class BufferAttribute {
    constructor(array: ArrayLike<number>, itemSize: number);
    count: number;
    itemSize: number;
    needsUpdate: boolean;
    getX(index: number): number;
    getY(index: number): number;
    getZ(index: number): number;
  }

  export class BufferGeometry {
    setAttribute(name: string, attribute: BufferAttribute): this;
    getAttribute(name: string): BufferAttribute | undefined;
    dispose(): void;
  }

  export class TorusKnotGeometry extends BufferGeometry {
    constructor(
      radius?: number,
      tube?: number,
      tubularSegments?: number,
      radialSegments?: number,
      p?: number,
      q?: number,
    );
  }

  export interface Uniforms {
    [name: string]: { value: unknown };
  }

  export class Material {
    dispose(): void;
  }

  export interface ShaderMaterialParameters {
    uniforms?: Uniforms;
    vertexShader?: string;
    fragmentShader?: string;
    transparent?: boolean;
    blending?: number;
    depthTest?: boolean;
    depthWrite?: boolean;
    wireframe?: boolean;
  }

  export class ShaderMaterial extends Material {
    constructor(parameters?: ShaderMaterialParameters);
    uniforms: Uniforms;
  }

  export interface PointsMaterialParameters {
    color?: number | Color;
    size?: number;
    sizeAttenuation?: boolean;
    transparent?: boolean;
    opacity?: number;
    blending?: number;
    depthTest?: boolean;
    depthWrite?: boolean;
  }

  export class PointsMaterial extends Material {
    constructor(parameters?: PointsMaterialParameters);
  }

  export class Object3D {
    position: Vector3;
    rotation: Euler;
    add(...objects: Object3D[]): this;
  }

  export class Mesh extends Object3D {
    constructor(geometry?: BufferGeometry, material?: Material);
    geometry: BufferGeometry;
    material: Material;
  }

  export class Points extends Object3D {
    constructor(geometry?: BufferGeometry, material?: Material);
    geometry: BufferGeometry;
    material: Material;
  }

  export class Scene extends Object3D {}

  export class PerspectiveCamera extends Object3D {
    constructor(fov?: number, aspect?: number, near?: number, far?: number);
    aspect: number;
    updateProjectionMatrix(): void;
  }

  export interface WebGLRendererParameters {
    canvas?: HTMLCanvasElement;
    alpha?: boolean;
    antialias?: boolean;
    powerPreference?: "default" | "high-performance" | "low-power";
  }

  export class WebGLRenderer {
    constructor(parameters?: WebGLRendererParameters);
    domElement: HTMLCanvasElement;
    setPixelRatio(value: number): void;
    setSize(width: number, height: number, updateStyle?: boolean): void;
    setClearColor(color: number | Color, alpha?: number): void;
    render(scene: Scene, camera: PerspectiveCamera): void;
    dispose(): void;
    forceContextLoss(): void;
  }
}

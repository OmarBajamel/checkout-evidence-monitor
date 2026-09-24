// Adapted from shadcn/ui Button, MIT, source SHA98a1fe67b439324ddc857f47fbdce056600a4329.
// Original CEM classes replace upstream theme tokens; see THIRD_PARTY_NOTICES.md.
import * as React from 'react';
import {Slot} from '@radix-ui/react-slot';
import {cva,type VariantProps} from 'class-variance-authority';
import {clsx} from 'clsx';
const variants=cva('button',{variants:{variant:{default:'button-primary',outline:'button-outline',ghost:'button-ghost',danger:'button-danger'},size:{default:'',small:'button-small'}},defaultVariants:{variant:'default',size:'default'}});
export function Button({className,variant,size,asChild=false,...props}:React.ComponentProps<'button'>&VariantProps<typeof variants>&{asChild?:boolean}){
  const Comp=asChild?Slot:'button';
  return <Comp data-slot="button" className={clsx(variants({variant,size}),className)} {...props}/>;
}

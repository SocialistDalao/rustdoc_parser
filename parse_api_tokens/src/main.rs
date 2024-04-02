#![feature(rustc_private)]

extern crate rustc_driver;
extern crate rustc_error_codes;
extern crate rustc_errors;
extern crate rustc_hash;
extern crate rustc_hir;
extern crate rustc_interface;
extern crate rustc_session;
extern crate rustc_span;
extern crate rustc_lexer;

use std::{path, process, str};

use rustc_errors::registry;
use rustc_hash::{FxHashMap, FxHashSet};
use rustc_session::config::{self, CheckCfg};
use rustc_span::source_map;
use rustc_lexer::tokenize;

extern crate syn;

use syn::{Item, ReturnType, Type, parse_quote};

fn main() {
    let input = "fn hello()";
    for token in tokenize(input) {
        println!("{:?}", token);
    }
    let out = process::Command::new("rustc")
        .arg("--print=sysroot")
        .current_dir(".")
        .output()
        .unwrap();
    let sysroot = str::from_utf8(&out.stdout).unwrap().trim();
    let config = rustc_interface::Config {
        // Command line options
        opts: config::Options {
            maybe_sysroot: Some(path::PathBuf::from(sysroot)),
            ..config::Options::default()
        },
        // cfg! configuration in addition to the default ones
        crate_cfg: FxHashSet::default(), // FxHashSet<(String, Option<String>)>
        crate_check_cfg: CheckCfg::default(), // CheckCfg
        input: config::Input::Str {
            name: source_map::FileName::Custom("main.rs".into()),
            input: r#"
            fn intersperse(self, separator: Self::Item) -> Intersperse<Self> where Self::Item: Clone;
"#
            .into(),
        },
        output_dir: None,  // Option<PathBuf>
        output_file: None, // Option<PathBuf>
        file_loader: None, // Option<Box<dyn FileLoader + Send + Sync>>
        locale_resources: rustc_driver::DEFAULT_LOCALE_RESOURCES,
        lint_caps: FxHashMap::default(), // FxHashMap<lint::LintId, lint::Level>
        // This is a callback from the driver that is called when [`ParseSess`] is created.
        parse_sess_created: None, //Option<Box<dyn FnOnce(&mut ParseSess) + Send>>
        // This is a callback from the driver that is called when we're registering lints;
        // it is called during plugin registration when we have the LintStore in a non-shared state.
        //
        // Note that if you find a Some here you probably want to call that function in the new
        // function being registered.
        register_lints: None, // Option<Box<dyn Fn(&Session, &mut LintStore) + Send + Sync>>
        // This is a callback from the driver that is called just after we have populated
        // the list of queries.
        //
        // The second parameter is local providers and the third parameter is external providers.
        override_queries: None, // Option<fn(&Session, &mut ty::query::Providers<'_>, &mut ty::query::Providers<'_>)>
        // Registry of diagnostics codes.
        registry: registry::Registry::new(&rustc_error_codes::DIAGNOSTICS),
        make_codegen_backend: None,
    };
    rustc_interface::run_compiler(config, |compiler| {
        compiler.enter(|queries| {
            // Parse the program and print the syntax tree.
            let parse = queries.parse().unwrap().get_mut().clone();
            println!("{parse:#?}");
            // Analyze the program and inspect the types of definitions.
            queries.global_ctxt().unwrap().enter(|tcx| {
                for id in tcx.hir().items() {
                    let hir = tcx.hir();
                    let item = hir.item(id);
                    match item.kind {
                        rustc_hir::ItemKind::Static(_, _, _) | rustc_hir::ItemKind::Fn(_, _, _) => {
                            let name = item.ident;
                            let ty = tcx.type_of(item.hir_id().owner.def_id);
                            println!("{name:?}:\t{ty:?}")
                        }
                        _ => (),
                    }
                }
            })
        });
    });



    let api_sig1 = "fn add(a: i32, b: i32) -> i32;";
    let api_sig2 = "fn add(a: i32, b: i32) -> i32;";

    if compare_api_signatures(api_sig1, api_sig2) {
        println!("API signatures are equivalent");
    } else {
        println!("API signatures are not equivalent");
    }
}


fn parse_api_signature(signature: &str) -> Result<Item, syn::Error> {
    syn::parse_str(signature)
}

fn compare_api_signatures(sig1: &str, sig2: &str) -> bool {
    let item1 = match parse_api_signature(sig1) {
        Ok(item) => item,
        Err(_) => return false, // Return false if parsing fails
    };
    let item2 = match parse_api_signature(sig2) {
        Ok(item) => item,
        Err(_) => return false, // Return false if parsing fails
    };

    // Compare relevant parts of the API signatures
    match (&item1, &item2) {
        (Item::Fn(item_fn1), Item::Fn(item_fn2)) => {
            // Compare function names
            if item_fn1.sig.ident != item_fn2.sig.ident {
                return false;
            }

            // Compare parameter types
            if item_fn1.sig.inputs.len() != item_fn2.sig.inputs.len() {
                return false;
            }
            for (param1, param2) in item_fn1.sig.inputs.iter().zip(item_fn2.sig.inputs.iter()) {
                if !compare_types(&param1, &param2) {
                    return false;
                }
            }

            // Compare return types
            if !compare_return_types(&item_fn1.sig.output, &item_fn2.sig.output) {
                return false;
            }

            // Compare generics if needed

            // If all comparisons passed, return true
            true
        }
        _ => false, // Return false if items are not functions
    }
}

fn compare_types(type1: &syn::FnArg, type2: &syn::FnArg) -> bool {
    // Compare types of function arguments
    // Implement as needed
    true
}

fn compare_return_types(type1: &ReturnType, type2: &ReturnType) -> bool {
    // Compare return types of functions
    // Implement as needed
    true
}

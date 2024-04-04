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

use std::{path, process, str, vec};

use rustc_errors::registry;
use rustc_hash::{FxHashMap, FxHashSet};
use rustc_session::config::{self, CheckCfg};
use rustc_span::source_map;
use rustc_lexer::tokenize;

extern crate syn;

use syn::{parse_quote, Item, ItemImpl, ReturnType, Type};
use std::fs::File;
use std::io::prelude::*;

mod json;
use json::{read_json, write_json};

fn main() {
    // let input = "fn hello()";
    // for token in tokenize(input) {
    //     println!("{:?}", token);
    // }

    test_single_func_parse();
    // test_parse_compare();

}

fn test_full_parse(){
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
            fn intersperse(self, separator: Self::Item) -> Intersperse<Self> where Self::Item: Clone;"#
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
}


/// Things to consider:
/// 1. Name: Impl trait name, function name, impl object name.
/// 2. Generics: Type parameters, lifetime parameters.
/// 3. Inputs: Function inputs.
/// 4. Output: Function output.
/// 
/// Algorithm:
/// 1. Generics are tied with name, inputs and output. 
///     We need to first construct the relation between generics and modifiers, regardless of the name and senquence of declaration.
/// 2. We ignore all WhereClause as it is hard to compare and can crash the comparison.
/// 
/// Implementation:
/// 1. Input: Json files of all plain APIs.
/// 2.1 Parsing: Do the plain parsing of all APIs.
/// 2.2 Detailed Parsing: If no matching API, try to parse the API in detail. Generics and lifetime are taken into consideration.
/// 3. Output: Overwrite the Json files with the detailed parsing.
fn test_single_func_parse(){
    // let api = "impl<I> Iterator for Intersperse<I> where I: Iterator, <I as Iterator>::Item: Clone, type Item = <I as Iterator>::Item{}";// `type cannot be successfully resolved
    // let api = "impl<I> Iterator for Intersperse<I> where I: Iterator, <I as Iterator>::Item: Clone{}";

    fn create_file(filename: &str, content: &str) {
        let mut file = File::create(filename).expect("Failed to create file");
        file.write_all(content.as_bytes()).expect("Failed to write to file");
    }
    let file1 = "output1.txt";
    let file2 = "output2.txt";
    // let api1 = "impl<T, '_> Iterator for Drain<'_, T>{}";
    // let api2 = "impl<'_, T> Iterator for Drain<'_, T>{}";
    // let api1 = "impl<T, U> Into for T where U: From<T>{}";
    // let api2 = "impl<T, U> Into<U> for T where U: From<T>{}";
    // let api1 = "impl<'a, F> Pattern for F where F: FnMut(char) -> bool{}";
    // let api2 = "impl<'a, F> Pattern<'a> for F where F: FnMut(char) -> bool{}";
    // let api1 = "impl<'a, T> Iterator for Drain<'a, T>{}";
    // let api2 = "impl<T, '_> Iterator for Drain<'_, T>{}";
    // let api1 = "impl<K: Ord, Q: ?Sized, V, '_> Index<&'_ Q> for BTreeMap<K, V> where K: Borrow<Q>, Q: Ord{}";
    // let api2 = "impl<'_, K: Ord, Q: ?Sized, V> Index<&'_ Q> for BTreeMap<K, V> where K: Borrow<Q>, Q: Ord{}";
    // let api1 = "impl<'_> Add<&'_ Wrapping<i128>> for Wrapping<i128>{}";
    // let api2 = "impl Add<&'_ Wrapping<i128>> for Wrapping<i128>{}";
    // let api1 = "impl<'a> Neg for &'a Wrapping<usize>{}";
    // let api2 = "impl<'_> Neg for &'_ Wrapping<usize>{}";
    let api1 = "type Output = Wrapping<usize>::Output;";
    let api2 = "type Output = <Wrapping<usize> as Add<Wrapping<usize>>>::Output;";
    // let api1_sig = parse_api(api1).unwrap();
    // let api2_sig = parse_api(api2).unwrap();
    // println!("Equals: {:#?}", api1_sig == api2_sig);
    let item1:syn::Item = syn::parse_str(api1).expect("Failed to parse API signature");
    let item2:syn::Item = syn::parse_str(api2).expect("Failed to parse API signature");
    create_file(file1, format!("{:#?}", item1).as_str());
    create_file(file2, format!("{:#?}", item2).as_str());
    // println!("Equals: {:#?}", item1 == item2);
    // println!("Equals: {:#?}", api1_sig == api2_sig);

}

#[derive(Debug, PartialEq, Eq)]
pub struct ApiSignature {
    pub ty: String,
    pub name: String,
    pub impls: Option<syn::Path>,
    pub generics: Vec<Type>,
    pub inputs: Vec<String>,
    pub output: String,
}

impl ApiSignature {
    pub fn new() -> Self {
        ApiSignature {
            ty: String::new(),
            name: String::new(),
            impls: None,
            generics: Vec::new(),
            inputs: Vec::new(),
            output: String::new(),
        }
    }

    pub fn get_impl_name(&self) -> Option<String> {
        Some(self.impls.clone()?.segments[0].ident.to_string())
    }
}

fn parse_api(api: &str) -> Option<ApiSignature>{
    println!("Parsing API: {:#?}", api);
    let item1:syn::Item = syn::parse_str(api).expect("Failed to parse API signature");
    let mut api_signature = ApiSignature::new();
    println!("{:#?}", item1);
    match item1 {
        Item::Fn(item_fn) => {
            println!("Name: {:#?}", item_fn.sig.ident);
            println!("Generics: {:#?}", item_fn.sig.generics);
            println!("Inputs: {:#?}", item_fn.sig.inputs);
            println!("Output: {:#?}", item_fn.sig.output);
            // println!("Function inputs: {:?}", item_fn.sig.inputs);
            // println!("Function output: {:?}", item_fn.sig.output);
        }
        Item::Impl(item_impl) => {
            api_signature.impls = Some(item_impl.trait_?.1);
            println!("Generics: {:#?}", item_impl.generics.params);
            let target = item_impl.self_ty;
            {
                if let Type::Path(type_path) = *target {
                    api_signature.name = type_path.path.segments[0].ident.to_string();
                }
            }
            // println!("Target: {:#?}", target);
        }
        _ => return None,
    }
    return Some(api_signature);
}

